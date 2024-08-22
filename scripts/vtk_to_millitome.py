import trimesh
import argparse
import numpy as np
import pyvista as pv

from pathlib import Path

"""
This is the conversion script used for converting the ovary vtk into a processable and registrable geometry
"""

parser = argparse.ArgumentParser(description='Convert vtk to glb for the Millitome use case')
parser.add_argument('--vtk', 
                    dest='path_to_vtk',
                    default=Path(__file__).parent.parent.joinpath('data/Ovary/Source/ovary.vtk'),
                    help='Path to the .vtk file to convert')
parser.add_argument('--glb', 
                    dest='path_to_glb',
                    required=True,
                    help='Path to save the converted Millitome compatible .glb file')

args = parser.parse_args()

# check for the extension
if Path(args.path_to_glb).suffix != '.glb':
  raise ValueError("Please include the filename with the .glb extension as part of the path you provide")

# use pyvista to load the file
pyvista_mesh = pv.read(Path(args.path_to_vtk)).extract_surface()

# initialize a trimesh.base.Trimesh object from it
# the repository adopts trimesh.base.Trimesh objects as the prefered representation for meshes
# preserve order and ensure labels from the vtk file are transfered correctly
mesh = trimesh.Trimesh(vertices=pyvista_mesh.points,
                       faces=pyvista_mesh.regular_faces,
                       vertex_colors=trimesh.visual.interpolate(pyvista_mesh.active_scalars, color_map='viridis'),
                       process=False)

# extract the unique block colors (preserve order)
_, sort_index = np.unique(mesh.visual.vertex_colors, axis=0, return_index=True)
block_colors = mesh.visual.vertex_colors[np.sort(sort_index)]

# extract the indices of each block within the combined geometry
block_indices = [np.flatnonzero(np.all(mesh.visual.vertex_colors == block_color, axis=1)) for block_color in block_colors]

# extract the faces corresponding to each block
block_faces = [np.any(np.isin(mesh.faces, indices), axis=1) for indices in block_indices]

# extract the blocks using the obtained face sequences
blocks = [mesh.submesh([faces])[0] for faces in block_faces]

# merge back into a scene (but blocks separate and accessible)
# blocks are numbered as in the original .vtk file since the order is preserved
scene = trimesh.Scene()
for block_number, block in enumerate(blocks, start=1):
  scene.add_geometry(block, geom_name=str(block_number), node_name=str(block_number))

# export as .glb
scene.export(file_obj=Path(args.path_to_glb))
