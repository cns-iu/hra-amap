import subprocess
import numpy as np
import open3d as o3d

from hra_amap.registration.decorators import step
from hra_amap.registration.dataclass import Transform
from hra_amap.utils.conversions import (
    pointcloud_to_numpy,
    numpy_to_pointcloud,
    txt_to_numpy,
    pointcloud_to_mesh,
)
from hra_amap.utils.preprocess import scale, compute_features
import os
from pathlib import Path

BASE_DIR = Path.cwd()
BCPD_DIR = Path(os.getenv("BCPD_DIR", BASE_DIR / "bcpd"))


@step(
    name="Normalize ICP", description="Scale organs to a common range about the centre"
)
def normalize_rigid(source, target):
    """
    Normalize the source and target point clouds by scaling them to unit size and centering.

    Args:
        source (o3d.geometry.PointCloud): Source point cloud.
        target (o3d.geometry.PointCloud): Target point cloud.

    Returns:
        Tuple[Dict[str, o3d.geometry.PointCloud], Dict[str, Transform]]: Normalized outputs and applied transforms.
    """
    # scale
    source_scale = scale(source, method="unit")
    target_scale = scale(target, method="unit")

    # create transform
    source_transform = Transform(scale=source_scale)
    target_transform = Transform(scale=target_scale)

    # apply
    source, target = source_transform(source, center=True), target_transform(
        target, center=True
    )

    # store outputs
    outputs = {"Source": source, "Target": target}

    # store transforms
    transforms = {"Source": source_transform, "Target": target_transform}

    return (outputs, transforms)


@step(
    name="Flip",
    description="Flip organ about the Y-axis to account for Left and Reft organ differences",
)
def flip(source, target):
    raise NotImplementedError


@step(
    name="Global Registration",
    description="Initial, fast registration before rigid registration",
)
def global_registration(source, target, params):
    """
    Perform global registration using RANSAC on FPFH features.

    Args:
        source (o3d.geometry.PointCloud): Source point cloud.
        target (o3d.geometry.PointCloud): Target point cloud.
        params (Dict): Dictionary of registration parameters.

    Returns:
        Tuple[None, Dict[str, Transform]]: No output geometry yet; only initial transform for refinement.
    """
    distance_threshold = (
        params["voxel_size"] * params["global_distance_threshold_factor"]
    )

    # downsample
    source = source.voxel_down_sample(params["voxel_size"])
    target = target.voxel_down_sample(params["voxel_size"])

    # compute features
    source_fpfh_features = compute_features(source, params)
    target_fpfh_features = compute_features(target, params)

    # register
    result = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        source,
        target,
        source_fpfh_features,
        target_fpfh_features,
        True,
        distance_threshold,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
        3,
        [
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(
                params["global_edge_length_threshold_factor"]
            ),
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(
                distance_threshold
            ),
        ],
        o3d.pipelines.registration.RANSACConvergenceCriteria(
            params["global_max_iterations"], params["global_max_correspondence"]
        ),
    )

    # store transforms (no need to apply transform since this will be directly used to refine the registation)
    transforms = {
        "Source": Transform(matrix=result.transformation, apply=False),
        "Target": None,
    }

    return (None, transforms)


@step(
    name="Rigid Registration",
    description="Registeration using only rigid transformations (scale, translation and rotation)",
)
def refine_registration(source, target, params, transform):
    """
    Perform rigid registration using ICP (point-to-plane) to refine alignment.

    Args:
        source (o3d.geometry.PointCloud): Source point cloud.
        target (o3d.geometry.PointCloud): Target point cloud.
        params (Dict): Dictionary of refinement parameters.
        transform (Dict[str, Transform]): Initial transformation from global registration.

    Returns:
        Tuple[Dict[str, o3d.geometry.PointCloud], Dict[str, Transform]]: Refined source and applied transform.
    """

    distance_threshold = (
        params["voxel_size"] * params["refine_distance_threshold_factor"]
    )

    # register
    result = o3d.pipelines.registration.registration_icp(
        source,
        target,
        distance_threshold,
        transform["Source"].matrix,
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
    )

    # create transform
    transform = Transform(matrix=result.transformation)

    # apply transform
    source = transform(source)

    # store outputs
    outputs = {"Source": source, "Target": None}

    # store transforms
    transforms = {"Source": transform, "Target": None}

    return (outputs, transforms)


@step(
    name="Normalize BCPD",
    description="Normalize location and scale before nonrigid registration",
)
def normalize_nonrigid(source, target):
    """
    Normalize the scale and center of both source and target before nonrigid registration.

    Args:
        source (o3d.geometry.PointCloud): Source point cloud.
        target (o3d.geometry.PointCloud): Target point cloud.

    Returns:
        Tuple[Dict[str, o3d.geometry.PointCloud], Dict[str, Transform]]: Normalized point clouds and transforms.
    """
    # calculate scale
    source_scale = scale(source, method="stddev")
    target_scale = scale(target, method="stddev")

    # create transform
    source_transform = Transform(scale=source_scale)
    target_transform = Transform(scale=target_scale)

    # apply
    source, target = source_transform(source, center=True), target_transform(
        target, center=True
    )

    # store outputss
    outputs = {"Source": source, "Target": target}

    # store transforms
    transforms = {"Source": source_transform, "Target": target_transform}

    return (outputs, transforms)


import os


@step(
    name="Non-rigid Registration",
    description="Registration using rigid and non-rigid (local deformations) with BCPD algorithm",
)
def nonrigid_registration(source, target, params):
    """
    Perform non-rigid registration using the BCPD algorithm, allowing local deformations.

    Args:
        source (o3d.geometry.PointCloud): Source point cloud.
        target (o3d.geometry.PointCloud): Target point cloud.
        params (Dict): Parameters for BCPD execution and configuration.

    Returns:
        Tuple[Dict[str, o3d.geometry.PointCloud], Dict[str, Transform]]: Transformed source, registered output, and transforms.
    """
    # convert to array
    source_array = pointcloud_to_numpy(source)
    target_array = pointcloud_to_numpy(target)

    # # save the source and target point clouds as .txt
    np.savetxt(f"{BCPD_DIR}/source.txt", source_array, delimiter=",")
    np.savetxt(f"{BCPD_DIR}/target.txt", target_array, delimiter=",")

    # build registration args
    reigstration_args = [
        "./bcpd",
        "-x",
        f"{BCPD_DIR}/target.txt",
        "-y",
        f"{BCPD_DIR}/source.txt",
        "-J",
        "300",
        "-K",
        "70",
        "-p",
        "-u",
        "n",
        "-c",
        str(params["distance_threshold"]),
        "-r",
        str(params["seed"]),
        "-n",
        str(params["max_iterations"]),
        "-l",
        str(params["lambda"]),
        "-b",
        str(params["beta"]),
        "-s",
        "yxuveTY",
    ]

    # for rotation
    if "gamma" in params:
        reigstration_args.extend(["-g", str(params["gamma"])])

    # for downsampling acceleration
    # TODO: auto-detect when downsampling acceleration is needed instead of having it specified
    if "downsampling" in params:
        reigstration_args.extend(["-D", str(params["downsampling"])])

    # register using BCPD
    result = subprocess.run(reigstration_args, cwd=str(BCPD_DIR), capture_output=True)

    # read transformations
    if "downsampling" in params:
        downsampled_source = np.genfromtxt(BCPD_DIR / "output_normY.txt")
        dvf = np.genfromtxt(BCPD_DIR / "output_u.txt") - downsampled_source
    else:
        dvf = np.genfromtxt(BCPD_DIR / "output_u.txt") - source_array
    translation = txt_to_numpy(BCPD_DIR / "output_t.txt")
    scale = txt_to_numpy(BCPD_DIR / "output_s.txt").item()
    rotation = txt_to_numpy(BCPD_DIR / "output_r.txt")

    # create transform
    transform = Transform(
        scale=scale,
        rotate=rotation,
        translate=translation,
        deformation_vector_field=dvf,
    )

    # apply transform and store outputs
    if "downsampling" in params:
        # this automatically calculates and stores an interpolated DVF to use with ANY geometry
        downsampled_source = transform(downsampled_source)
        # transform the original source using the interpolated DVF calculated
        source = transform(source)
        registered = numpy_to_pointcloud(
            txt_to_numpy(BCPD_DIR / "output_y.interpolated.txt")
        )
    else:
        source = transform(source)
        registered = numpy_to_pointcloud(txt_to_numpy(BCPD_DIR / "output_y.txt"))

    # store outputs
    outputs = {"Source": source, "Target": None, "Registered": registered}

    # store transforms
    transforms = {"Source": transform, "Target": None}

    return (outputs, transforms)


@step(name="Denormalization BCPD", description="Denormalize the organ after projection")
def denormalize_nonrigid(source, target, transforms):
    """
    Revert the normalization applied before nonrigid registration.

    Args:
        source (o3d.geometry.PointCloud): Source point cloud after registration.
        target (o3d.geometry.PointCloud): Target point cloud after registration.
        transforms (Dict[str, Transform]): Transform used during normalization.

    Returns:
        Tuple[Dict[str, o3d.geometry.PointCloud], Dict[str, Transform]]: Denormalized point clouds and transforms.
    """
    # apply
    source, target = transforms["Target"].invert(source), transforms["Target"].invert(
        target
    )

    # store outputs
    outputs = {"Source": source, "Target": target}

    # store transforms
    transforms = {"Source": transforms["Target"], "Target": transforms["Target"]}

    return (outputs, transforms)


@step(name="Denormalization ICP", description="Denormalize the organ after projection")
def denormalize_rigid(source, target, transforms):
    """
    Revert the normalization applied before rigid (ICP) registration.

    Args:
        source (o3d.geometry.PointCloud): Source point cloud after registration.
        target (o3d.geometry.PointCloud): Target point cloud after registration.
        transforms (Dict[str, Transform]): Transform used during normalization.

    Returns:
        Tuple[Dict[str, o3d.geometry.PointCloud], Dict[str, Transform]]: Denormalized point clouds and transforms.
    """
    # apply
    source, target = transforms["Target"].invert(source), transforms["Target"].invert(
        target
    )

    # store outputs
    outputs = {"Source": source, "Target": target}

    # store transforms
    transforms = {"Source": transforms["Target"], "Target": transforms["Target"]}

    return (outputs, transforms)
