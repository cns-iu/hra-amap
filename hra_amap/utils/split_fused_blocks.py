import trimesh
import numpy as np
import scipy.ndimage as ndi

from tqdm import tqdm
from trimesh.smoothing import filter_taubin
from trimesh.voxel import VoxelGrid

def make_cutting_mesh(mesh,
                      target_voxels=200,
                      fill_hole_radius=10,
                      erosion_iterations=5,
                      smoothing_iterations=100):
  # voxelization of combined mesh
  pitch = mesh.extents.max() / target_voxels
  vg = mesh.voxelized(pitch).fill()
  M = vg.matrix.astype(bool)

  # seal openings
  selem = ndi.generate_binary_structure(3, 1)
  selem = ndi.iterate_structure(selem, fill_hole_radius)
  M_closed = ndi.binary_closing(M, structure=selem)

  # fill internals
  M_solid = ndi.binary_fill_holes(M_closed)

  # erode
  M_inner = ndi.binary_erosion(M_solid, iterations=erosion_iterations)

  # convert back to mesh
  inner_vg = VoxelGrid(M_inner, transform=vg.transform)
  inner_mesh = inner_vg.marching_cubes.copy()
  inner_mesh.apply_transform(inner_vg.transform)

  # smoothen the voxelized mesh
  filter_taubin(inner_mesh, lamb=0.5, nu=-0.53, iterations=smoothing_iterations)

  return inner_mesh

# load model
mesh = trimesh.load('/Users/bhargavdesai/Desktop/uterus-millitome.glb')
# convert blocks to convex hulls
blocks = [block.convex_hull for _, block in mesh.geometry.items()]

# combined mesh
combined_mesh = trimesh.util.concatenate(blocks)

# create cutting mesh from combined mesh
cutting_mesh = make_cutting_meshq(combined_mesh, target_voxels=200, erosion_iterations=2)


updated_blocks = {}
# iterate over blocks and split where needed
for id, block in tqdm(mesh.geometry.items()):
  # convert blocks to convex hulls
  block = block.convex_hull
  id = id.split('-')
  if len(id) > 1:
    # slice
    outer_block = trimesh.boolean.difference([block, cutting_mesh])
    inner_block = trimesh.boolean.intersection([block, cutting_mesh])

    # add color
    outer_block.visual.face_colors = [255, 0, 0, 150]
    inner_block.visual.face_colors = [0, 0, 255, 150]

    # update
    updated_blocks.update({id[0]: outer_block})
    updated_blocks.update({id[1]: inner_block})

  else:
    block.visual.face_colors = [255, 255, 0, 150]
    updated_blocks.update({id[0]: block})

scene = trimesh.Scene(updated_blocks)
_ = scene.export('./uterus-cut.glb')
