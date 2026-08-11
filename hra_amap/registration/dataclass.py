import pickle
import trimesh
import numpy as np
import open3d as o3d
import gzip

from typing import Optional
from dataclasses import dataclass
from hra_amap.utils.preprocess import mean
from hra_amap.utils.conversions import to_array, to_pointcloud, to_mesh

from copy import deepcopy
from pathlib import Path
from scipy.spatial.transform import Rotation
from scipy.interpolate import NearestNDInterpolator


@dataclass
class Transform:
    """
    Handles transformation of 3D geometries using scale, rotation, translation,
    and optionally deformation vector fields (DVF).
    """

    scale: tuple = (1, 1, 1)
    rotate: Optional[np.ndarray | tuple] = (0, 0, 0)
    translate: tuple = (0, 0, 0)
    deformation_vector_field: Optional[np.ndarray] = None
    deformation_source: Optional[np.ndarray] = None
    matrix: np.ndarray = None
    rotate_axes: str = "xyz"
    apply: bool = True

    def __post_init__(self):
        if isinstance(self.matrix, np.ndarray):
            pass
        else:
            # check if scale is a float or an int
            scale_array = (
                [self.scale] * 3 if isinstance(self.scale, (float, int)) else self.scale
            )
            # check if rotation is a matrix or tuple of angles
            if isinstance(self.rotate, (tuple, list)):
                # find rotation matrix from angles if tuple or list
                rotation_matrix = Rotation.from_euler(
                    seq=self.rotate_axes, angles=self.rotate, degrees=True
                ).as_matrix()
            else:
                rotation_matrix = self.rotate
            # construct a 4x4 transformation matrix
            self.matrix = np.empty((4, 4))
            self.matrix[:3, :3] = rotation_matrix @ np.diagflat(scale_array)
            self.matrix[:3, 3] = self.translate
            self.matrix[3, :] = [0, 0, 0, 1]

    def transform(self, geometry, invert=False):
        """
        Applies transformation matrix to geometry.
        """
        if isinstance(geometry, o3d.geometry.PointCloud):
            return geometry.transform(self.matrix if not invert else self.inverse)
        else:
            return geometry.apply_transform(self.matrix if not invert else self.inverse)

    def invert(self, geometry):
        """
        Applies inverse transformation to geometry.
        """
        if isinstance(self.deformation_vector_field, np.ndarray):
            raise ValueError("Inversion not supported on DVF transformations")
        self.inverse = np.linalg.inv(self.matrix)
        geometry = self.transform(geometry, invert=True)
        if hasattr(self, "centered"):
            array = to_array(geometry) + self.mean
            geometry = (
                to_pointcloud(array)
                if isinstance(geometry, o3d.geometry.PointCloud)
                else to_mesh(array, geometry.faces)
            )
        return geometry

    def center(self, geometry):
        """
        Centers geometry based on its mean position.
        """
        self.centered = True
        if not hasattr(self, "mean"):
            self.mean = mean(geometry)
        array = to_array(geometry) - self.mean
        geometry = (
            to_pointcloud(array)
            if isinstance(geometry, o3d.geometry.PointCloud)
            else to_mesh(array, geometry.faces)
        )
        return geometry

    def __call__(self, geometry, center=False):
        """
        Applies transformation (and optionally centering) to a geometry.
        """
        if hasattr(self, "centered") or center == True:
            geometry = self.center(geometry)
        if isinstance(self.deformation_vector_field, np.ndarray):
            geometry = to_array(geometry)
            if not hasattr(self, "interpolated_dvf"):
                source = (
                    self.deformation_source
                    if isinstance(self.deformation_source, np.ndarray)
                    else geometry
                )
                self.interpolated_dvf = NearestNDInterpolator(
                    source, self.deformation_vector_field
                )
            geometry = (
                (geometry + self.interpolated_dvf(geometry)) @ np.asarray(self.rotate).T
            ) * self.scale + self.translate
            return to_pointcloud(geometry)
        else:
            return self.transform(geometry)


@dataclass
class PipelineStep:
    """
    Container for a single step in a transformation pipeline.
    """

    name: str
    description: Optional[str] = None
    input: o3d.geometry.PointCloud = None
    output: o3d.geometry.PointCloud = None
    transform: Optional[dict[Transform]] = None
    logs: Optional[str] = None


@dataclass
class Projection:
    """
    Stores metadata and methods to project a geometry from source to target.
    """

    id: str
    description: str
    source: "Organ"
    target: "Organ"
    transformations: list[dict[Transform]]
    registration: trimesh.base.Trimesh
    params: dict
    metadata: dict = None

    @classmethod
    def load(cls, path: str):
        """
        Load a projection object from a gzip-compressed pickle file.
        """
        with gzip.open(path, "rb") as file:
            obj = pickle.load(file)
        return obj

    def export(self, path: str):
        """
        Save the projection object to a gzip-compressed pickle file.
        """
        parent_dir = Path(path)
        parent_dir.mkdir(parents=True, exist_ok=True)

        with gzip.open(parent_dir / "projections.pickle.gz", "wb") as file:
            pickle.dump(self, file)

    def _copy_geometry(self, geometry):
        out = type(geometry)(
            vertices=np.array(geometry.vertices, copy=True),
            faces=np.array(geometry.faces, copy=True),
        )
        for attr in (
            "target_transform",
            "transform",
            "division_factor",
            "label",
            "donor",
            "metadata",
            "target_name",
        ):
            if hasattr(geometry, attr):
                setattr(out, attr, getattr(geometry, attr))
        return out

    def _project_points(self, points):
        pointcloud = to_pointcloud(np.asarray(points, dtype=np.float64))

        for _, transform in self.transformations:
            if transform.apply:
                pointcloud = (
                    transform(pointcloud)
                    if not hasattr(transform, "inverse")
                    else transform.invert(pointcloud)
                )

        return np.asarray(pointcloud.points, dtype=np.float64)

    def _dense_sample(self, geometry):
        samples_per_axis = (
            self.params.get("projection", {}).get("dense_samples_per_axis", 5)
        )
        if isinstance(samples_per_axis, int):
            samples_per_axis = (samples_per_axis,) * 3

        vertices = np.asarray(geometry.vertices, dtype=np.float64)
        center = vertices.mean(axis=0)
        centered = vertices - center
        _, _, axes = np.linalg.svd(centered, full_matrices=False)
        axes = axes.T
        local = centered @ axes
        grids = [
            np.linspace(local[:, axis].min(), local[:, axis].max(), samples_per_axis[axis])
            for axis in range(3)
        ]
        sample_local = np.asarray(np.meshgrid(*grids, indexing="ij")).reshape(3, -1).T
        return sample_local @ axes.T + center

    @staticmethod
    def _fit_similarity(source, target):
        source = np.asarray(source, dtype=np.float64)
        target = np.asarray(target, dtype=np.float64)
        source_center = source.mean(axis=0)
        target_center = target.mean(axis=0)
        source_centered = source - source_center
        target_centered = target - target_center
        covariance = source_centered.T @ target_centered / len(source)
        u, singular_values, vt = np.linalg.svd(covariance)
        correction = np.eye(3)
        if np.linalg.det(vt.T @ u.T) < 0:
            correction[-1, -1] = -1
        rotation = vt.T @ correction @ u.T
        variance = np.mean(np.sum(source_centered**2, axis=1))
        scale = np.trace(np.diag(singular_values) @ correction) / max(variance, 1e-12)
        translation = target_center - scale * (source_center @ rotation)
        return scale, rotation, translation

    @staticmethod
    def _apply_similarity(points, scale, rotation, translation):
        return scale * (np.asarray(points, dtype=np.float64) @ rotation) + translation

    def _project_tissue_block(self, geometry):
        sample_points = self._dense_sample(geometry)
        projected_samples = self._project_points(sample_points)
        scale, rotation, translation = self._fit_similarity(
            sample_points, projected_samples
        )
        projected = self._copy_geometry(geometry)
        projected.vertices = self._apply_similarity(
            geometry.vertices, scale, rotation, translation
        )
        return projected

    def _is_tissue_block(self, geometry):
        return hasattr(geometry, "target_transform") and hasattr(geometry, "division_factor")

    def project(self, geometry):
        if self._is_tissue_block(geometry):
            return self._project_tissue_block(geometry)

        # get pointcloud
        # TO DO: make concatenated transforms work on Tissue / Organ objects as well
        # currently, they work on pointclouds and arrays only
        if hasattr(geometry, "pointcloud"):
            pointcloud = deepcopy(geometry.pointcloud)
        else:
            pointcloud = to_pointcloud(geometry)

        for _, transform in self.transformations:
            # apply projections
            if transform.apply:
                pointcloud = (
                    transform(pointcloud)
                    if not hasattr(transform, "inverse")
                    else transform.invert(pointcloud)
                )

        # move pointcloud back to hra target position
        if hasattr(geometry, "target_transform"):
            pointcloud = (
                geometry.target_transform(pointcloud)
                if geometry.target_transform
                else pointcloud
            )

        # assign the transformation to the geometry object
        if isinstance(geometry, trimesh.base.Trimesh):
            geometry.vertices = np.array(pointcloud.points)

        return geometry
