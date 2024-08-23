import subprocess
import numpy as np
import open3d as o3d

from decorators import step
from dataclass import Transform
from utils.conversions import pointcloud_to_numpy, numpy_to_pointcloud, txt_to_numpy, pointcloud_to_mesh
from utils.preprocess import scale, compute_features

@step(name='Normalize ICP', description='Scale organs to a common range about the centre')
def normalize_rigid(source, target):
    # scale
    source_scale = scale(source, method='unit') 
    target_scale = scale(target, method='unit')    

    # create transform
    source_transform = Transform(scale=source_scale)
    target_transform = Transform(scale=target_scale)

    # apply
    source, target = source_transform(source, center=True), target_transform(target, center=True)

    # store outputs
    outputs = {'Source': source, 'Target': target}
    
    # store transforms
    transforms = {'Source': source_transform, 'Target': target_transform}
    
    return (outputs, transforms)

@step(name='Flip', description='Flip organ about the Y-axis to account for Left and Reft organ differences')
def flip(source, target):
    raise NotImplementedError

@step(name='Global Registration', description='Initial, fast registration before rigid registration')
def global_registration(source, target, params):
    distance_threshold = params['voxel_size'] * params['global_distance_threshold_factor']
    
    # downsample
    source = source.voxel_down_sample(params['voxel_size'])
    target = target.voxel_down_sample(params['voxel_size'])

    # compute features
    source_fpfh_features = compute_features(source, params)
    target_fpfh_features = compute_features(target, params)

    # register
    result = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(source, 
                                                                                      target, 
                                                                                      source_fpfh_features,
                                                                                      target_fpfh_features, 
                                                                                      True, 
                                                                                      distance_threshold,
                                                                                      o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 
                                                                                      3,
                                                                                      [o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(params['global_edge_length_threshold_factor']), 
                                                                                       o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(distance_threshold)], 
                                                                                      o3d.pipelines.registration.RANSACConvergenceCriteria(params['global_max_iterations'], params['global_max_correspondence']))
    

    # store transforms (no need to apply transform since this will be directly used to refine the registation)
    transforms = {'Source': Transform(matrix=result.transformation, apply=False), 
                  'Target': None}    
    
    return (None, transforms)

@step(name='Rigid Registration', description='Registeration using only rigid transformations (scale, translation and rotation)')
def refine_registration(source, target, params, transform):
    distance_threshold = params['voxel_size'] * params['refine_distance_threshold_factor']

    # register
    result = o3d.pipelines.registration.registration_icp(source, 
                                                         target, 
                                                         distance_threshold, 
                                                         transform['Source'].matrix, 
                                                         o3d.pipelines.registration.TransformationEstimationPointToPlane())
    
    # create transform
    transform = Transform(matrix=result.transformation)
    
    # apply transform
    source = transform(source)
    
    # store outputs
    outputs = {'Source': source, 
              'Target': None}
    
    # store transforms
    transforms = {'Source': transform, 
                  'Target': None}
    
    return (outputs, transforms)

@step(name='Normalize BCPD', description='Normalize location and scale before nonrigid registration')
def normalize_nonrigid(source, target):
    # calculate scale
    source_scale = scale(source, method='stddev')
    target_scale = scale(target, method='stddev')

    # create transform
    source_transform = Transform(scale=source_scale)
    target_transform = Transform(scale=target_scale)

    # apply
    source, target = source_transform(source, center=True), target_transform(target, center=True)

    # store outputss
    outputs = {'Source': source, 
              'Target': target}
    
    # store transforms
    transforms = {'Source': source_transform, 
                  'Target': target_transform}
    
    return (outputs, transforms)

@step(name='Non-rigid Registration', description='Registration using rigid and non-rigid (local deformations) with BCPD algorithm')
def nonrigid_registration(source, target, params):
    # convert to array
    source_array = pointcloud_to_numpy(source)
    target_array = pointcloud_to_numpy(target)

    # save the source and target point clouds as .txt
    np.savetxt(f"../bcpd/source.txt", source_array, delimiter=',')
    np.savetxt(f"../bcpd/target.txt", target_array, delimiter=',')

    # build registration args 
    reigstration_args = ['./bcpd', 
                         '-x', f"../bcpd/target.txt", 
                         '-y', f"../bcpd/source.txt", 
                         '-J', '300', 
                         '-K', '70', 
                         '-p', '-u', 'n', 
                         '-c', str(params['distance_threshold']), 
                         '-r', str(params['seed']), 
                         '-n', str(params['max_iterations']), 
                         '-l', str(params['lambda']), 
                         '-b', str(params['beta']),
                         '-s', 'yxuveTY']

    # for rotation
    if 'gamma' in params:
        reigstration_args.extend(['-g', str(params['gamma'])])

    # for downsampling acceleration
    # TODO: auto-detect when downsampling acceleration is needed instead of having it specified
    if 'downsampling' in params:
        reigstration_args.extend(['-D', str(params['downsampling'])])

    # register using BCPD
    result = subprocess.run(reigstration_args, cwd="../bcpd", capture_output=True)
    
    # read transformations
    if 'downsampling' in params:
        downsampled_source = np.genfromtxt('../bcpd/output_normY.txt')
        dvf = np.genfromtxt('../bcpd/output_u.txt') - downsampled_source
    else:
        dvf = np.genfromtxt('../bcpd/output_u.txt') - source_array
    translation = txt_to_numpy('../bcpd/output_t.txt')
    scale = txt_to_numpy('../bcpd/output_s.txt').item()
    rotation = txt_to_numpy('../bcpd/output_r.txt')
    
    # create transform
    transform = Transform(scale=scale, rotate=rotation, translate=translation, deformation_vector_field=dvf)

    # apply transform and store outputs
    if 'downsampling' in params:
        # this automatically calculates and stores an interpolated DVF to use with ANY geometry
        downsampled_source = transform(downsampled_source)
        # transform the original source using the interpolated DVF calculated
        source = transform(source)
        registered = numpy_to_pointcloud(txt_to_numpy('../bcpd/output_y.interpolated.txt'))
    else:
        source = transform(source)
        registered = numpy_to_pointcloud(txt_to_numpy('../bcpd/output_y.txt'))

    # store outputs
    outputs = {'Source': source, 
               'Target': None, 
               'Registered': registered}
    
    # store transforms
    transforms = {'Source': transform,
                  'Target': None}
    
    return (outputs, transforms)

@step(name='Denormalization BCPD', description='Denormalize the organ after projection')
def denormalize_nonrigid(source, target, transforms):
    # apply
    source, target = transforms['Target'].invert(source), transforms['Target'].invert(target)

    # store outputs
    outputs = {'Source': source, 
              'Target': target}
    
    # store transforms
    transforms = {'Source': transforms['Target'],
                  'Target': transforms['Target']}
    
    return (outputs, transforms)

@step(name='Denormalization ICP', description='Denormalize the organ after projection')
def denormalize_rigid(source, target, transforms):
    # apply
    source, target = transforms['Target'].invert(source), transforms['Target'].invert(target)

    # store outputs
    outputs = {'Source': source, 
              'Target': target}
    
    # store transforms
    transforms = {'Source': transforms['Target'],
                  'Target': transforms['Target']}
    
    return (outputs, transforms)


