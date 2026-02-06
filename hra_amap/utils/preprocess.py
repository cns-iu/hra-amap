"""
This module provides geometric utilities for computing point cloud statistics,
scaling factors, and extracting geometric features such as FPFH (Fast Point Feature Histograms).
"""

import numpy as np
import open3d as o3d
import trimesh
import requests
from cgi import parse_header
from pathlib import Path
from io import BytesIO
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


def download_and_process_glb_file(
    glb_url: str, raw_data_dir: Path, retain: list = None, timeout: int = 30
):
    """
    Download the GLB file from the given URL, optionally filter geometries based on retain component list, and save locally.
    Returns the saved file path or None if failed.
    """
    try:
        response = requests.get(glb_url, stream=True, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to download GLB file from {glb_url}: {e}")
        return None

    raw_data_dir.mkdir(parents=True, exist_ok=True)

    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        _, params = parse_header(content_disposition)
        file_name = params.get("filename", Path(glb_url).name)
    else:
        file_name = Path(glb_url).name

    glb_path = raw_data_dir / file_name

    try:
        if retain:
            glb_data = BytesIO(response.content)
            try:
                scene = trimesh.load(glb_data, file_type="glb")
            except Exception as e:
                print(f"Failed to load GLB: {e}")
                return None

            if isinstance(scene, trimesh.Scene):
                filtered_scene = trimesh.Scene()
                for node_name in retain:
                    if node_name in scene.geometry:
                        filtered_scene.add_geometry(
                            scene.geometry[node_name], node_name=node_name
                        )

                if not filtered_scene.geometry:
                    print(
                        f"No geometries matched retain list {retain}. Saving original GLB."
                    )
                    Path(glb_path).write_bytes(response.content)
                else:
                    with open(glb_path, "wb") as f:
                        filtered_scene.export(f, file_type="glb")
            else:
                print("The loaded GLB is not a scene. Saving original file.")
                Path(glb_path).write_bytes(response.content)
        else:
            with open(glb_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"GLB file saved to {glb_path}")
        return glb_path

    except Exception as e:
        print(f"Error processing GLB file: {e}")
        return None
