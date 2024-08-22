import json
import yaml
import trimesh
import open3d as o3d

from pathlib import Path
from datetime import datetime

from utils.conversions import pointcloud_to_mesh, ply_to_mesh, nii_to_mesh, vtk_to_mesh

def load(file_name: str, file_type: str) -> trimesh.Trimesh:
    """Loads a mesh from a local path"""
    if file_type in ['.glb', '.stl', '.obj', '.fbx']:
        mesh = trimesh.load(file_name, file_type, force='mesh')
    elif file_type == '.pcd':
        mesh = pointcloud_to_mesh(o3d.io.read_point_cloud(f"{file_name}{file_type}"))
    elif file_type == '.ply':
        mesh = ply_to_mesh(o3d.io.read_triangle_mesh(f"{file_name}{file_type}"))
    elif file_type in ['.nii', '.nii.gz']:
        mesh = nii_to_mesh(f"{file_name}{file_type}")
    elif file_type == '.vtk':
        mesh = vtk_to_mesh(file_name)

    return (mesh.faces, mesh.vertices)

def read_json(path: str) -> dict:
    """Reads a JSON file, returns a Python Dict object"""
    with open(path) as f:
        file = json.load(f)
    return file

def write_json(path: str, data):
    # write to json
    with open(path, 'w') as f:
        json.dump(data, f, indent='\t')

def read_yaml(path: str) -> dict:
    """Reads a YAML file, returns a Python Dict object"""
    with open(path, "r") as f:
        file = yaml.safe_load(f)
    return file

def write_yaml(path: str, data):
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

def add_header(file_path: str):
    header = '# yaml-language-server: $schema=https://raw.githubusercontent.com/hubmapconsortium/hra-rui-locations-processor/main/registrations.schema.json'
    # read file
    with open(file_path, 'r') as f:
            text = f.read()

    # append header
    text = header + "\n" + "\n" + text

    # write file
    with open(file_path, "w") as f:
        f.write(text)
