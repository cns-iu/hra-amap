import sys

import time
import trimesh
import numpy as np
from copy import deepcopy
from tqdm.auto import tqdm
from pathlib import Path
import json
from datetime import date
from hra_amap.utils.constants import ConfigKeys


def build_mesh_from_sample(sample, scaling_factor):
    """
    Builds a 3D box mesh from a sample's RUI location metadata, applying unit conversion,
    scaling, rotation, and translation to place the mesh correctly in 3D space.

    Args:
        sample (dict): Sample record containing RUI location, spatial dimensions,
                       placement information, and associated metadata.
        scaling_factor (float): Scaling factor applied to convert spatial units into
                                the target coordinate system.

    Returns:
        trimesh.Trimesh: A transformed 3D box mesh representing the sample geometry.
    """
    rui = sample[ConfigKeys.RUI_LOCATION_KEY]
    mustard = np.array([225, 173, 1, 255], dtype=np.uint8)

    units = rui.get('dimension_units', 'millimeter')
    factor = 1e3 if units == 'millimeter' else 1e2 if units == 'centimeter' else 1.0

    size = (
        rui['x_dimension'] / factor * scaling_factor,
        rui['y_dimension'] / factor * scaling_factor,
        rui['z_dimension'] / factor * scaling_factor,
    )

    mesh = trimesh.creation.box(extents=size)
    mesh.metadata['sample'] = sample
    mesh.metadata['id'] = sample.get(ConfigKeys.AT_ID)
    mesh.metadata['donor'] = sample.get('donor')
    mesh.metadata['label'] = sample.get('label')
    mesh.metadata['sample_type'] = sample.get('sample_type')

    placement = rui.get(ConfigKeys.PLACEMENT, {})
    if placement:
        rx = np.deg2rad(placement.get('x_rotation', 0))
        ry = np.deg2rad(placement.get('y_rotation', 0))
        rz = np.deg2rad(placement.get('z_rotation', 0))
        rot = trimesh.transformations.euler_matrix(rx, ry, rz, axes='sxyz')
        mesh.apply_transform(rot)

        tx = placement.get('x_translation', 0) / factor * scaling_factor
        ty = placement.get('y_translation', 0) / factor * scaling_factor
        tz = placement.get('z_translation', 0) / factor * scaling_factor
        mesh.apply_translation([tx, ty, tz])

    mesh.visual.vertex_colors = np.tile(mustard, (mesh.vertices.shape[0], 1))
    return mesh

def scale_millitome_block(blocks, scale):
    """
    Uniformly scale all blocks about their collective centroid.
    Preserves relative positions and orientations.
    """
    center = np.mean([b.centroid for b in blocks], axis=0)

    for b in blocks:
        b.apply_scale(scale)

        offset = b.centroid - center
        b.apply_translation(offset * (scale - 1))

def filter_samples(data, filter):
    """
    Filters donor samples based on RUI placement target using sex, organ name, and version criteria.

    Args:
        data (list): List of donor records containing sample metadata.
        filter (dict): Filter configuration containing sex, organ name, and version.

    Returns:
        list: List of donors with samples matching the specified filter criteria.
    """
    filtered = []
    for donor in tqdm(data):
        filtered_samples = []
        for sample in donor['samples']:
            if ConfigKeys.RUI_LOCATION_KEY in sample and ConfigKeys.PLACEMENT in sample[ConfigKeys.RUI_LOCATION_KEY] and ConfigKeys.TARGET in sample[ConfigKeys.RUI_LOCATION_KEY][ConfigKeys.PLACEMENT]:
                target = sample[ConfigKeys.RUI_LOCATION_KEY][ConfigKeys.PLACEMENT][ConfigKeys.TARGET].split('#')[-1]
                # filter
                filter_str = 'VH'+''.join([filter[ConfigKeys.SEX], filter['name']])
                if filter['version'] == 'All':
                    if filter_str in target:
                        filtered_samples.append(sample)
                if filter['version'] == 'Latest':
                    if filter_str == target:
                        filtered_samples.append(sample)
                else:
                    filter_str = filter_str + filter['version']
                    if filter_str == target:
                        filtered_samples.append(sample)
        if filtered_samples:
            donor['samples'] = filtered_samples
            filtered.append(donor)

    return filtered

def build_blocks_and_donor_points(donors, scaling_factor):
    """
    Builds 3D block meshes from donor samples and computes corresponding
    donor placement points in scaled coordinates.

    Args:
        donors (list): List of donor records containing samples and metadata.
        scaling_factor (float): Scaling factor applied to spatial dimensions.

    Returns:
        tuple:
            - blocks (list[trimesh.Trimesh]): Generated block meshes with metadata attached.
            - donor_points (np.ndarray): Array of donor placement points (N x 3).
    """
    blocks = []
    donor_points = []

    for donor in donors:
        for sample in donor['samples']:
            # Build block mesh from sample
            mesh = build_mesh_from_sample(sample, scaling_factor)

            # Attach donor-level metadata
            mesh.metadata.update({
                'label': donor.get('label'),
                '@id': donor.get(ConfigKeys.AT_ID),
                '@type': donor.get('@type'),
                'consortium_name': donor.get('consortium_name'),
                'sex': donor.get(ConfigKeys.SEX),
                'provider_name': donor.get('provider_name'),
                'provider_uuid': donor.get('provider_uuid'),
                'link': donor.get(ConfigKeys.LINK),
                'description': donor.get('description'),
            })

            blocks.append(mesh)

            # Compute donor placement point
            placement = sample[ConfigKeys.RUI_LOCATION_KEY].get(ConfigKeys.PLACEMENT, {})
            units = sample[ConfigKeys.RUI_LOCATION_KEY].get('dimension_units', 'millimeter')
            factor = 1e3 if units == 'millimeter' else 1e2 if units == 'centimeter' else 1.0

            donor_points.append([
                placement.get('x_translation', 0) / factor * scaling_factor,
                placement.get('y_translation', 0) / factor * scaling_factor,
                placement.get('z_translation', 0) / factor * scaling_factor,
            ])

    return blocks, np.array(donor_points)

def generate_extraction_sites_jsonld_from_blocks(blocks, context, config_dict, output_path):
    today = date.today().isoformat()
    entities = []

    for i, block in enumerate(blocks):
        sample = block.metadata.get("sample", {})
        rui = sample.get(ConfigKeys.RUI_LOCATION_KEY, {})

        block_id = block.metadata.get("id", f"block_{i}")
        label = block_id.split("#")[-1]


        entity = {
            "@context": context,
            "@id": block_id,
            "@type": rui.get("@type"),
            "label": label,

            "creator": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator"),
            "creator_first_name": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator_first_name"),
            "creator_last_name": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator_last_name"),
            "creator_orcid": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator_orcid"),
            "creation_date": today,

            "x_dimension": rui.get("x_dimension"),
            "y_dimension": rui.get("y_dimension"),
            "z_dimension": rui.get("z_dimension"),
            "dimension_units": rui.get("dimension_units", "millimeter"),

            "placement": rui.get(ConfigKeys.PLACEMENT, {}),

            "ccf_annotations": rui.get("ccf_annotations", [])
        }

        entities.append(entity)
    with open(output_path, "w") as f:
        json.dump(entities, f, indent=2)

    print(f"\n JSON-LD written to: {output_path}")

def generate_dataset_graph_jsonld_from_blocks(blocks, context, config_dict, source_graph, output_path):

    today = date.today().isoformat()

    donor_lookup = {}
    for item in source_graph:
        if item.get("@type") == "Donor":
            donor_lookup[item["@id"]] = item

    millitome_graph = []

    for block in blocks:
        sample = block.metadata.get("sample", {})
        donor_url = block.metadata.get("donor")

        if not donor_url:
            continue

        donor_obj = donor_lookup.get(donor_url, {})

        millitome_donor = {
            "@id": block.metadata.get('donor'),
            "@type": block.metadata.get('@type'),
            "label": str(donor_obj.get(ConfigKeys.LABEL, "")),
            "description": donor_obj.get("description", ""),
            "link": block.metadata.get(ConfigKeys.LINK),
            "consortium_name": donor_obj.get("consortium_name"),
            "provider_name": donor_obj.get("provider_name"),
            "provider_uuid": donor_obj.get("provider_uuid"),
            "sex": donor_obj.get(ConfigKeys.SEX),
            "samples": []
        }

        sample_id = sample.get("@id")
        rui = sample.get(ConfigKeys.RUI_LOCATION_KEY, {})

        spatial_entity = {
            "@context": context,
            "@id": block.metadata.get(ConfigKeys.AT_ID),
            "@type": "SpatialEntity",
            "label": sample_id.split('#')[-1],

            "creator": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator"),
            "creator_first_name": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator_first_name"),
            "creator_last_name": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator_last_name"),
            "creator_orcid": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator_orcid"),
            "creation_date": today,

            "x_dimension": rui.get("x_dimension"),
            "y_dimension": rui.get("y_dimension"),
            "z_dimension": rui.get("z_dimension"),
            "dimension_units": rui.get("dimension_units", "millimeter"),

            "placement": rui.get(ConfigKeys.PLACEMENT, {}),

            "ccf_annotations": rui.get("ccf_annotations", [])
        }

        sample_entry = {
            "@id": sample.get(ConfigKeys.AT_ID),
            "@type": sample.get('@type'),
            "sample_type": sample.get("sample_type", "Tissue Block"),
            "label": sample.get(ConfigKeys.LABEL, ""),
            "description": sample.get('description'),
            "link": sample.get(ConfigKeys.LINK),
            "section_count": sample.get('section_count', 0), 
            "section_size": sample.get("section_size", 0),
            ConfigKeys.RUI_LOCATION_KEY: spatial_entity
        }

        millitome_donor["samples"].append(sample_entry)

        millitome_graph.append(millitome_donor)

    dataset_graph = {
        "@context": context,
        "@graph": millitome_graph
    }

    with open(output_path, "w") as f:
        json.dump(dataset_graph, f, indent=2)