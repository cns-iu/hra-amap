import hashlib
import json
import trimesh
import numpy as np
import open3d as o3d
from pathlib import Path

from hra_amap.utils.io import load
from hra_amap.utils.conversions import to_array, to_pointcloud
from hra_amap.utils.progress import tqdm_or_iter


DEFAULT_VISUAL_HULL_PARAMS = {
    "target_grid": 120,
    "image_size": 420,
    "force_rebuild": False,
}


class Organ(trimesh.Trimesh):
    """
    A 3D organ model that inherits from trimesh and supports transformations,
    point cloud access, and coordinate alignment with the Human Reference Atlas (HRA).
    """

    def __init__(
        self,
        path: str,
        target_name: str = None,
        metadata: dict = None,
        volumetric: bool = False,
        visual_hull_params: dict = None,
        progress: bool = False,
    ) -> None:
        """
        Initialize the Organ object.

        Args:
            path (str): Path to the 3D organ file.
            target_name (str): Target organ name used for retrieving HRA transformation info.
            metadata (dict, optional): Additional metadata.
        """
        super(Organ, self).__init__()
        self.metadata = metadata or {}
        self.path = Path(path)
        self.target_name = target_name
        self.name = self.path.stem
        self.file_type = self.path.suffix if self.path.suffix else ".glb"
        self.volumetric = volumetric
        self.visual_hull_params = {
            **DEFAULT_VISUAL_HULL_PARAMS,
            **(visual_hull_params or {}),
        }
        self.progress = progress
        self._visual_hull_volume_points = None
        self._visual_hull_stats = None
        self.surface_count = 0

        self.faces, self.vertices = load(self.path, self.file_type)
        self.surface_count = len(self.vertices)
        # self.target_transform = None

    @property
    def pointcloud(self):
        """Convert the organ mesh to an Open3D point cloud."""
        return to_pointcloud(self.registration_vertices)

    @property
    def array(self):
        """Return the organ mesh as a NumPy array of vertices."""
        return to_array(self.registration_vertices)

    @property
    def registration_vertices(self):
        if not self.volumetric:
            return np.asarray(self.vertices, dtype=np.float64)
        return np.vstack(
            [
                np.asarray(self.vertices, dtype=np.float64),
                self.visual_hull_volume_points,
            ]
        )

    @property
    def visual_hull_volume_points(self):
        if self._visual_hull_volume_points is None:
            self._visual_hull_volume_points = self._visual_hull()
        return self._visual_hull_volume_points

    @property
    def visual_hull_stats(self):
        if self._visual_hull_stats is None:
            _ = self.visual_hull_volume_points
        return self._visual_hull_stats

    def _cache_dir(self):
        cache_dir = self.visual_hull_params.get("cache_dir")
        if cache_dir:
            return Path(cache_dir)
        return Path.cwd().resolve().parent / "cache" / "visual-hulls"

    def _cache_stem(self):
        params = {
            key: value
            for key, value in self.visual_hull_params.items()
            if key not in {"cache_dir", "force_rebuild"}
        }
        payload = {
            "geometry_sha1": self._geometry_hash(),
            "params": params,
        }
        digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return f"organ__{digest[:16]}"

    def _geometry_hash(self):
        digest = hashlib.sha1()
        digest.update(np.ascontiguousarray(self.vertices, dtype=np.float64).tobytes())
        digest.update(np.ascontiguousarray(self.faces, dtype=np.int64).tobytes())
        return digest.hexdigest()

    def _visual_hull(self):
        cache_dir = self._cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        stem = self._cache_stem()
        volume_path = cache_dir / f"{stem}_volume.npy"
        stats_path = cache_dir / f"{stem}_stats.json"

        if (
            volume_path.exists()
            and stats_path.exists()
            and not self.visual_hull_params.get("force_rebuild")
        ):
            self._visual_hull_stats = json.loads(stats_path.read_text())
            self._visual_hull_stats["cached"] = True
            if self.progress:
                print(f"Loading cached visual hull: {self.name}")
            return np.load(volume_path)

        volume_points, stats = self._calculate_visual_hull()
        np.save(volume_path, volume_points)
        stats_path.write_text(json.dumps(stats, indent=2))
        self._visual_hull_stats = stats
        return volume_points

    def _calculate_visual_hull(self):
        cubic_size = 2.0
        voxel_resolution = int(self.visual_hull_params["target_grid"])
        image_size = int(self.visual_hull_params["image_size"])
        voxel_size = cubic_size / voxel_resolution

        mesh, center, scale = self._preprocess_o3d_model(self._to_o3d_mesh())
        camera_sphere = self._preprocess_o3d_model(
            o3d.geometry.TriangleMesh.create_sphere()
        )[0]

        voxel_carving = o3d.geometry.VoxelGrid.create_dense(
            width=cubic_size,
            height=cubic_size,
            depth=cubic_size,
            voxel_size=voxel_size,
            origin=[-cubic_size / 2.0] * 3,
            color=[1.0, 0.0, 0.0],
        )

        vis = o3d.visualization.Visualizer()
        vis.create_window(width=image_size, height=image_size, visible=False)
        vis.add_geometry(mesh)
        vis.get_render_option().mesh_show_back_face = True
        view_control = vis.get_view_control()
        camera = view_control.convert_to_pinhole_camera_parameters()
        pointcloud = o3d.geometry.PointCloud()

        views = list(camera_sphere.vertices)
        try:
            for xyz in tqdm_or_iter(
                views,
                progress=self.progress,
                desc=f"Calculating visual hull: {self.name}",
                unit="view",
                leave=False,
            ):
                camera.extrinsic = self._camera_extrinsic(xyz)
                view_control.convert_from_pinhole_camera_parameters(camera)
                vis.poll_events()
                vis.update_renderer()
                depth = vis.capture_depth_float_buffer(False)
                if int((np.asarray(depth) > 0).sum()) == 0:
                    raise ValueError(f"{self.name}: Open3D rendered an empty view.")

                image = o3d.geometry.Image(depth)
                pointcloud += o3d.geometry.PointCloud.create_from_depth_image(
                    image,
                    camera.intrinsic,
                    camera.extrinsic,
                    depth_scale=1,
                )
                voxel_carving.carve_silhouette(image, camera)

                if len(voxel_carving.get_voxels()) == 0:
                    raise ValueError(f"{self.name}: Open3D carving removed all voxels.")
        finally:
            vis.destroy_window()

        min_bound = [-cubic_size / 2.0] * 3
        max_bound = [cubic_size / 2.0] * 3
        voxel_surface = o3d.geometry.VoxelGrid.create_from_point_cloud_within_bounds(
            pointcloud,
            voxel_size=voxel_size,
            min_bound=min_bound,
            max_bound=max_bound,
        )

        voxel_grid = voxel_surface + voxel_carving
        indices = np.asarray(
            [voxel.grid_index for voxel in voxel_grid.get_voxels()],
            dtype=np.float64,
        ).reshape((-1, 3))
        if len(indices) == 0:
            raise ValueError(f"{self.name}: Open3D voxel carving produced zero voxels.")

        points = (
            np.asarray(voxel_grid.origin, dtype=np.float64)
            + (indices + 0.5) * float(voxel_grid.voxel_size)
        )
        volume_points = points * float(scale) + np.asarray(center, dtype=np.float64)
        stats = {
            "volume_points": int(len(volume_points)),
            "surface_points": int(len(self.vertices)),
            "control_points": int(len(self.vertices) + len(volume_points)),
            "grid": int(voxel_resolution),
            "camera_views": int(len(views)),
            "camera_source": "o3d.geometry.TriangleMesh.create_sphere()",
            "image_size": int(image_size),
            "cached": False,
        }
        return volume_points, stats

    def _to_o3d_mesh(self):
        mesh = o3d.geometry.TriangleMesh()
        mesh.vertices = o3d.utility.Vector3dVector(
            np.asarray(self.vertices, dtype=np.float64)
        )
        mesh.triangles = o3d.utility.Vector3iVector(
            np.asarray(self.faces, dtype=np.int32)
        )
        mesh.compute_vertex_normals()
        return mesh

    @staticmethod
    def _preprocess_o3d_model(model):
        min_bound = model.get_min_bound()
        max_bound = model.get_max_bound()
        center = min_bound + (max_bound - min_bound) / 2.0
        scale = np.linalg.norm(max_bound - min_bound) / 2.0
        model.vertices = o3d.utility.Vector3dVector(
            (np.asarray(model.vertices) - center) / scale
        )
        return model, center, scale

    @staticmethod
    def _spherical(xyz):
        x, y, z = xyz
        radius = np.sqrt(x * x + y * y + z * z)
        return [radius, np.arccos(y / radius), np.arctan2(z, x)]

    @classmethod
    def _camera_extrinsic(cls, xyz):
        _, rx, ry = cls._spherical(xyz)
        rot_x = np.asarray(
            [
                [1, 0, 0],
                [0, np.cos(rx), -np.sin(rx)],
                [0, np.sin(rx), np.cos(rx)],
            ]
        )
        rot_y = np.asarray(
            [
                [np.cos(ry), 0, np.sin(ry)],
                [0, 1, 0],
                [-np.sin(ry), 0, np.cos(ry)],
            ]
        )
        extrinsic = np.eye(4)
        extrinsic[:3, :3] = rot_y.dot(rot_x)
        extrinsic[:3, 3] = np.asarray([0, 0, 2]).T
        return extrinsic
