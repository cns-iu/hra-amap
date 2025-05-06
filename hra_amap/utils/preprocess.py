"""
This module provides geometric utilities for computing point cloud statistics,
scaling factors, and extracting geometric features such as FPFH (Fast Point Feature Histograms).
"""

import numpy as np
import open3d as o3d

from hra_amap.utils.conversions import to_array, to_mesh, to_pointcloud


def mean(geometry):
    """
    Computes the centroid (mean position) of the input geometry.

    Parameters:
    - geometry: A numpy array, Open3D point cloud, or trimesh mesh.

    Returns:
    - np.ndarray: A 3-element array representing the mean x, y, z coordinates.
    """
    return to_array(geometry).mean(axis=0)


def scale(geometry, method="unit"):
    """
    Computes a scaling factor for the geometry based on the selected method.

    Parameters:
    - geometry: A numpy array, Open3D point cloud, or trimesh mesh.
    - method (str): Scaling method. Options are:
        - "unit": scales based on the bounding box diagonal.
        - "stddev": scales based on standard deviation from the centroid.

    Returns:
    - float: The computed scale factor.
    """
    if method == "unit":
        scale = 1 / np.max(
            to_pointcloud(geometry).get_max_bound()
            - to_pointcloud(geometry).get_min_bound()
        )
    if method == "stddev":
        center = mean(geometry)
        array = to_array(geometry)
        scale = 1 / (
            np.sqrt(
                np.sum(np.square(array - center) / (array.shape[0] * array.shape[1]))
            )
        )
    return scale


def compute_features(pointcloud, params):
    """
    Computes FPFH (Fast Point Feature Histograms) features for a given point cloud.

    Parameters:
    - pointcloud (o3d.geometry.PointCloud): The input point cloud.
    - params (dict): Dictionary with keys:
        - "voxel_size" (float): Used to determine search radii.
        - "max_nn" (int): Maximum nearest neighbors to use for search.

    Returns:
    - o3d.pipelines.registration.Feature: Extracted FPFH features.
    """
    # estimate normals
    radius_normal = params["voxel_size"] * 2
    pointcloud.estimate_normals(
        o3d.geometry.KDTreeSearchParamHybrid(
            radius=radius_normal, max_nn=params["max_nn"]
        )
    )

    # compute features
    radius_feature = params["voxel_size"] * 5
    fpfh_features = o3d.pipelines.registration.compute_fpfh_feature(
        pointcloud,
        o3d.geometry.KDTreeSearchParamHybrid(
            radius=radius_feature, max_nn=params["max_nn"]
        ),
    )

    return fpfh_features
