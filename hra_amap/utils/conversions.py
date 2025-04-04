import trimesh
import numpy as np
import pandas as pd
import pyvista as pv
import open3d as o3d

from pathlib import Path
from scipy.spatial.transform import Rotation as R
from sklearn.preprocessing import normalize

def split_transform(matrix):
    # retrieve the translation
    translation = matrix[:3, 3]

    # retrieve the rotation matrix
    rotation_matrix = matrix[:3, :3]

    # retrieve the scale from the rotation matrix
    scale = np.linalg.norm(rotation_matrix, axis=0)

    # retrive the rotation from the rotation matrix
    rotation = normalize(rotation_matrix, axis=0, norm='l2')
    rotation = R.from_matrix(rotation).as_euler('xyz', degrees=True)

    return (scale, rotation, translation)

def to_array(geometry):
    if isinstance(geometry, o3d.geometry.PointCloud):
        return pointcloud_to_numpy(geometry)
    elif isinstance(geometry, trimesh.base.Trimesh):
        return mesh_to_numpy(geometry)
    else: 
        return geometry
    
def to_pointcloud(geometry):
    if isinstance(geometry, np.ndarray):
        return numpy_to_pointcloud(geometry)
    elif isinstance(geometry, trimesh.base.Trimesh):
        return mesh_to_pointcloud(geometry)
    else: 
        return geometry
    
def to_mesh(geometry, faces, process=True):
    if isinstance(geometry, np.ndarray):
        return numpy_to_mesh(geometry, faces, process)
    elif isinstance(geometry, o3d.geometry.PointCloud):
        return pointcloud_to_mesh(geometry, faces, process)
    else: 
        return geometry

def mesh_to_pointcloud(mesh: trimesh.base.Trimesh) -> o3d.geometry.PointCloud:
    """Converts a trimesh mesh object to an open3d compatible point cloud"""
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.array(mesh.vertices))
    pcd.estimate_normals()
    return pcd

def mesh_to_numpy(mesh: trimesh.Trimesh) -> np.ndarray:
    """Converts a trimesh mesh object to a numpy array"""
    return np.array(mesh.vertices)

def numpy_to_pointcloud(numpy_array: np.ndarray) -> o3d.geometry.PointCloud:
    """Converts a numpy array to an open3d compatible point cloud"""
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(numpy_array)
    pcd.estimate_normals()
    return pcd

def numpy_to_mesh(numpy_array: np.ndarray, faces: np.ndarray, process=True) -> trimesh.base.Trimesh:
    return trimesh.Trimesh(vertices=numpy_array, faces=faces, process=process)

def pointcloud_to_numpy(pointcloud: o3d.geometry.PointCloud) -> np.ndarray:
    return np.array(pointcloud.points)

def pointcloud_to_mesh(pointcloud: o3d.geometry.PointCloud, faces: np.ndarray, process=True) -> o3d.geometry.PointCloud:
    """Converts a open3d point cloud object to trimesh mesh object"""
    return trimesh.Trimesh(vertices=np.array(pointcloud.points), faces=faces, process=process)

def txt_to_numpy(path: str) -> np.ndarray:
    """Converts an array saved as a text to a numpy object"""
    return np.genfromtxt(path)

def txt_to_pandas(path: str) -> pd.DataFrame:
    # load the correspondences
    correspondences = np.genfromtxt(path, skip_header=1)
    df_corres = pd.DataFrame(correspondences, columns=['reference', 'source', 'prob'])
    
    # subtract 1 to adjust for python indexing
    df_corres.reference = df_corres['reference'] - 1
    df_corres.source = df_corres['source'] - 1
    return df_corres

def ply_to_mesh(path: str) -> trimesh.Trimesh:
    ply = o3d.io.read_triangle_mesh(path)
    return trimesh.Trimesh(vertices=np.array(ply.vertices), faces=np.array(ply.triangles))

def nii_to_mesh(path: str) -> trimesh.Trimesh:
    raise NotImplementedError

def vtk_to_mesh(path: str) -> trimesh.Trimesh:
    filename = Path(path)
    # use pyvista to load the file
    pyvista_mesh = pv.read(filename).extract_surface()

    # initialize a trimesh.base.Trimesh object from it
    # the repository adopts trimesh.base.Trimesh objects as the prefered representation for meshes
    # preserve order and ensure labels from the vtk file are transfered correctly
    mesh = trimesh.Trimesh(vertices=pyvista_mesh.points,
                           faces=pyvista_mesh.regular_faces,
                           vertex_colors=trimesh.visual.interpolate(pyvista_mesh.active_scalars, color_map='viridis'),
                           process=False)

    return mesh