import numpy as np
import open3d as o3d

from utils.conversions import to_array, to_mesh, to_pointcloud


def mean(geometry):
    return to_array(geometry).mean(axis=0)

def scale(geometry, method='unit'):
    if method == 'unit':
        scale = (1 / np.max(to_pointcloud(geometry).get_max_bound() - to_pointcloud(geometry).get_min_bound()))
    if method == 'stddev':
        center = mean(geometry)
        array = to_array(geometry)
        scale = (1 / (np.sqrt(np.sum(np.square(array - center) / (array.shape[0] * array.shape[1])))))
    return scale

def compute_features(pointcloud, params):
        # estimate normals
        radius_normal = params['voxel_size'] * 2
        pointcloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=radius_normal, 
                                                                         max_nn=params['max_nn']))

        # compute features
        radius_feature = params['voxel_size'] * 5
        fpfh_features = o3d.pipelines.registration.compute_fpfh_feature(pointcloud, 
                                                                        o3d.geometry.KDTreeSearchParamHybrid(radius=radius_feature, 
                                                                                                             max_nn=params['max_nn']))

        return fpfh_features