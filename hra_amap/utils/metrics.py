"""
This module provides utilities to compute geometric similarity metrics between 3D meshes
(such as Sinkhorn, Chamfer, and Hausdorff distances), as well as utilities for retrieving
anatomical transformation data from a remote knowledge graph.
"""

import numpy as np
import point_cloud_utils as pcu
import requests
import csv
import io

from functools import lru_cache
from hra_amap.utils.conversions import mesh_to_numpy


def sinkhorn(target_mesh, registered_mesh):
    """
    Computes the Sinkhorn distance between two simplified mesh geometries.

    Parameters:
    - target_mesh (trimesh.Trimesh): Reference mesh to compare against.
    - registered_mesh (trimesh.Trimesh): Mesh to evaluate the similarity with.

    Returns:
    - float: Sinkhorn distance between the two point sets.
    """
    dec_ref, dec_reg = target_mesh.simplify_quadratic_decimation(
        20000
    ), registered_mesh.simplify_quadratic_decimation(20000)
    a, b = mesh_to_numpy(dec_ref), mesh_to_numpy(dec_reg)

    # M is a 100x100 array where each entry  (i, j) is the L2 distance between point a[i, :] and b[j, :]
    M = pcu.pairwise_distances(a, b)

    # w_a and w_b are masses assigned to each point. In this case each point is weighted equally.
    w_a = np.ones(a.shape[0])
    w_b = np.ones(b.shape[0])

    # P is the transport matrix between a and b, eps is a regularization parameter, smaller epsilons lead to
    # better approximation of the true Wasserstein distance at the expense of slower convergence
    P = pcu.sinkhorn(w_a, w_b, M, eps=1e-3)

    # to get the distance as a number just compute the frobenius inner product <M, P>
    sinkhorn_dist = (M * P).sum()

    return sinkhorn_dist


def chamfer(target_mesh, registered_mesh):
    """
    Computes the Chamfer distance between two meshes.

    Parameters:
    - target_mesh (trimesh.Trimesh): Reference mesh to compare against.
    - registered_mesh (trimesh.Trimesh): Mesh to evaluate the similarity with.

    Returns:
    - float: Chamfer distance between the two point sets.
    """
    a = mesh_to_numpy(target_mesh)
    b = mesh_to_numpy(registered_mesh)
    chamfer_dist = pcu.chamfer_distance(a, b)
    return chamfer_dist


def hausdorff(target_mesh, registered_mesh):
    """
    Computes the Hausdorff distance between two meshes.

    Parameters:
    - target_mesh (trimesh.Trimesh): Reference mesh to compare against.
    - registered_mesh (trimesh.Trimesh): Mesh to evaluate the similarity with.

    Returns:
    - float: Hausdorff distance between the two point sets.
    """
    a = mesh_to_numpy(target_mesh)
    b = mesh_to_numpy(registered_mesh)
    hausdorff_dist = pcu.hausdorff_distance(a, b)
    return hausdorff_dist


def shape_complexity(mesh):
    raise NotImplementedError


scaling = [1.0, 1.0, 1.0]
rotation = [0.0, 0.0, 0.0]


def fetch_anatomical_structure():
    """
    Fetches anatomical structure transformation data via SPARQL query from the Human Reference Atlas API.

    Returns:
    - list[dict]: List of anatomical structure records with associated transform data.

    Raises:
    - Exception: If the request to the remote endpoint fails.
    """
    url = "https://grlc.io/api-git/hubmapconsortium/ccf-grlc/subdir/mesh-collision//anatomical-structures"
    params = {"endpoint": "https://lod.humanatlas.io/sparql"}
    headers = {"accept": "text/csv"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch hra_transforms: {response.status_code}")

    csv_data = list(csv.DictReader(io.StringIO(response.text)))
    return csv_data

@lru_cache()
def get_translations(target_name: str):
    """
    Retrieves translation vector for a given anatomical structure name by querying remote transformation data.

    Parameters:
    - target_name (str): Name of the anatomical structure.

    Returns:
    - list[float] | None: List of 3 float translation values (negated), or None if no match found.
    """
    hra_transforms = fetch_anatomical_structure()
    for row in hra_transforms:
        if (
            row['reference_organ'] == target_name
            and row['anatomical_structure_of'] == target_name
        ):
            return list(map(lambda x: -1 * float(x), list(row.values())[-3:]))
    return None
