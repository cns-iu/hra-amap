"""
The visual hull calculation here follows AND borrows most of the code from the Open3D voxel carving tutorial (see here:
https://www.open3d.org/docs/release/tutorial/geometry/voxelization.html#Voxel-carving)
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import open3d as o3d

from hra_amap.utils.progress import tqdm_or_iter


DEFAULT_VISUAL_HULL_PARAMS = {
    "target_grid": 120,
    "image_size": 420,
    "force_rebuild": False,
}


def visual_hull_volume_points(vertices, faces, name, params=None, progress=False):
    params = {**DEFAULT_VISUAL_HULL_PARAMS, **(params or {})}
    cache_dir = _cache_dir(params)
    cache_dir.mkdir(parents=True, exist_ok=True)
    stem = _cache_stem(vertices, faces, params)
    volume_path = cache_dir / f"{stem}_volume.npy"
    stats_path = cache_dir / f"{stem}_stats.json"

    if volume_path.exists() and stats_path.exists() and not params["force_rebuild"]:
        stats = json.loads(stats_path.read_text())
        stats["cached"] = True
        if progress:
            print(f"Loading cached visual hull: {name}")
        return np.load(volume_path), stats

    volume_points, stats = _calculate_visual_hull(vertices, faces, name, params, progress)
    np.save(volume_path, volume_points)
    stats_path.write_text(json.dumps(stats, indent=2))
    return volume_points, stats


def _cache_dir(params):
    return Path(
        params.get("cache_dir") or Path.cwd().resolve().parent / "cache" / "visual-hulls"
    )


def _cache_stem(vertices, faces, params):
    cached_params = {
        key: value
        for key, value in params.items()
        if key not in {"cache_dir", "force_rebuild"}
    }
    payload = {
        "geometry_sha1": _geometry_hash(vertices, faces),
        "params": cached_params,
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return f"organ__{digest[:16]}"


def _geometry_hash(vertices, faces):
    digest = hashlib.sha1()
    digest.update(np.ascontiguousarray(vertices, dtype=np.float64).tobytes())
    digest.update(np.ascontiguousarray(faces, dtype=np.int64).tobytes())
    return digest.hexdigest()


def _calculate_visual_hull(vertices, faces, name, params, progress):
    cubic_size = 2.0
    voxel_resolution = int(params["target_grid"])
    image_size = int(params["image_size"])
    voxel_size = cubic_size / voxel_resolution

    mesh, center, scale = _preprocess_o3d_model(_to_o3d_mesh(vertices, faces))
    camera_sphere = _preprocess_o3d_model(o3d.geometry.TriangleMesh.create_sphere())[0]

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
            progress=progress,
            desc=f"Calculating visual hull: {name}",
            unit="view",
            leave=False,
        ):
            camera.extrinsic = _camera_extrinsic(xyz)
            view_control.convert_from_pinhole_camera_parameters(camera)
            vis.poll_events()
            vis.update_renderer()
            depth = vis.capture_depth_float_buffer(False)
            if int((np.asarray(depth) > 0).sum()) == 0:
                raise ValueError(f"{name}: Open3D rendered an empty view.")

            image = o3d.geometry.Image(depth)
            pointcloud += o3d.geometry.PointCloud.create_from_depth_image(
                image,
                camera.intrinsic,
                camera.extrinsic,
                depth_scale=1,
            )
            voxel_carving.carve_silhouette(image, camera)

            if len(voxel_carving.get_voxels()) == 0:
                raise ValueError(f"{name}: Open3D carving removed all voxels.")
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
        raise ValueError(f"{name}: Open3D voxel carving produced zero voxels.")

    points = (
        np.asarray(voxel_grid.origin, dtype=np.float64)
        + (indices + 0.5) * float(voxel_grid.voxel_size)
    )
    volume_points = points * float(scale) + np.asarray(center, dtype=np.float64)
    stats = {
        "volume_points": int(len(volume_points)),
        "surface_points": int(len(vertices)),
        "control_points": int(len(vertices) + len(volume_points)),
        "grid": int(voxel_resolution),
        "camera_views": int(len(views)),
        "camera_source": "o3d.geometry.TriangleMesh.create_sphere()",
        "image_size": int(image_size),
        "cached": False,
    }
    return volume_points, stats


def _to_o3d_mesh(vertices, faces):
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(np.asarray(vertices, dtype=np.float64))
    mesh.triangles = o3d.utility.Vector3iVector(np.asarray(faces, dtype=np.int32))
    mesh.compute_vertex_normals()
    return mesh


def _preprocess_o3d_model(model):
    min_bound = model.get_min_bound()
    max_bound = model.get_max_bound()
    center = min_bound + (max_bound - min_bound) / 2.0
    scale = np.linalg.norm(max_bound - min_bound) / 2.0
    model.vertices = o3d.utility.Vector3dVector(
        (np.asarray(model.vertices) - center) / scale
    )
    return model, center, scale


def _spherical(xyz):
    x, y, z = xyz
    radius = np.sqrt(x * x + y * y + z * z)
    return [radius, np.arccos(y / radius), np.arctan2(z, x)]


def _camera_extrinsic(xyz):
    _, rx, ry = _spherical(xyz)
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
