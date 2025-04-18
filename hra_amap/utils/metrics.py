import numpy as np
import point_cloud_utils as pcu
import requests
import csv
import io

from hra_amap.utils.conversions import mesh_to_numpy

def sinkhorn(target_mesh, registered_mesh):
    dec_ref, dec_reg = target_mesh.simplify_quadratic_decimation(20000), registered_mesh.simplify_quadratic_decimation(20000)
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
    sinkhorn_dist = (M*P).sum()

    return sinkhorn_dist

def chamfer(target_mesh, registered_mesh):
    a = mesh_to_numpy(target_mesh)
    b = mesh_to_numpy(registered_mesh)
    chamfer_dist = pcu.chamfer_distance(a, b)
    return chamfer_dist
    
def hausdorff(target_mesh, registered_mesh):
    a = mesh_to_numpy(target_mesh)
    b = mesh_to_numpy(registered_mesh)
    hausdorff_dist = pcu.hausdorff_distance(a, b)
    return hausdorff_dist

def shape_complexity(mesh):
    raise NotImplementedError

scaling = [1.0,1.0,1.0]
rotation = [0.0,0.0,0.0]
def fetch_anatomical_structure():
    url = "https://grlc.io/api-git/hubmapconsortium/ccf-grlc/subdir/mesh-collision//anatomical-structures"
    params = {
        "endpoint": "https://lod.humanatlas.io/sparql"
    }
    headers = {
        "accept": "text/csv"
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch hra_transforms: {response.status_code}")

    csv_data = list(csv.DictReader(io.StringIO(response.text)))
    return csv_data

def get_translations(target_name : str):
    hra_transforms = fetch_anatomical_structure()
    for row in hra_transforms:
        if row[list(row.keys())[0]] == target_name and row[list(row.keys())[1]] == target_name:
            return list(row.values())[-3:]
    return None