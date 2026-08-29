import trimesh
import numpy as np
from pathlib import Path

from hra_amap.utils.io import load
from hra_amap.utils.conversions import to_array, to_pointcloud
from hra_amap.utils.visual_hull import visual_hull_volume_points


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
            (
                self._visual_hull_volume_points,
                self._visual_hull_stats,
            ) = visual_hull_volume_points(
                self.vertices,
                self.faces,
                self.name,
                progress=self.progress,
            )
        return self._visual_hull_volume_points

    @property
    def visual_hull_stats(self):
        if self._visual_hull_stats is None:
            _ = self.visual_hull_volume_points
        return self._visual_hull_stats
