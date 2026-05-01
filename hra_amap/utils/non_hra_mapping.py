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

def build_block_metadata(sample, donor):
    """
    Builds metadata from a sample's RUI location
    """

    rui = sample.get(ConfigKeys.RUI_LOCATION_KEY, {})
    placement = rui.get(ConfigKeys.PLACEMENT, {})

    units = rui.get("dimension_units", "millimeter")

    dimensions = (
        rui.get("x_dimension"),
        rui.get("y_dimension"),
        rui.get("z_dimension"),
    )

    placement_min = {
        "@id": placement.get("@id"),
        "@type": placement.get("@type", "SpatialPlacement"),
        "target": placement.get("target"),

        "x_rotation": placement.get("x_rotation", 0),
        "y_rotation": placement.get("y_rotation", 0),
        "z_rotation": placement.get("z_rotation", 0),

        "x_translation": placement.get("x_translation", 0),
        "y_translation": placement.get("y_translation", 0),
        "z_translation": placement.get("z_translation", 0),
    }

    rui_min = {
        "@id": rui.get("@id"),
        "@type": rui.get("@type", "SpatialEntity"),
        "dimension_units": units,

        "x_dimension": dimensions[0],
        "y_dimension": dimensions[1],
        "z_dimension": dimensions[2],

        "ccf_annotations": rui.get("ccf_annotations", []),

        ConfigKeys.PLACEMENT: placement_min,
    }

    sample_min = {
        "@id": sample.get("@id"),
        "@type": sample.get("@type", "Sample"),
        "sample_type": sample.get("sample_type"),
        "label": sample.get("label"),
        "description": sample.get("description"),
        "link": sample.get("link"),

        ConfigKeys.RUI_LOCATION_KEY: rui_min,
    }

    metadata = {
        "sample": sample_min,
        "id": sample.get(ConfigKeys.AT_ID),
        "donor": sample.get("donor"),
        "label": donor.get("label"),
        "@id": donor.get(ConfigKeys.AT_ID),
        "@type": donor.get("@type"),
        "consortium_name": donor.get("consortium_name"),
        "sex": donor.get(ConfigKeys.SEX),
        "provider_name": donor.get("provider_name"),
        "provider_uuid": donor.get("provider_uuid"),
        "link": donor.get(ConfigKeys.LINK),
        "description": donor.get("description"),
    }

    return metadata

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

def generate_extraction_sites_jsonld_from_blocks(
    blocks, context, config_dict, output_path
):
    today = date.today().isoformat()
    entities = []

    for i, block in enumerate(blocks):
        sample = block.metadata.get("sample", {})
        rui = sample.get(ConfigKeys.RUI_LOCATION_KEY, {})

        block_id = block.metadata.get("id", f"block_{i}")
        label = block_id

        entity = {
            "@context": context,
            "@id": block_id,
            "@type": rui.get("@type"),
            "label": label,
            "creator": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator"),
            "creator_first_name": config_dict[ConfigKeys.RUI_LOCATION_KEY].get(
                "creator_first_name"
            ),
            "creator_last_name": config_dict[ConfigKeys.RUI_LOCATION_KEY].get(
                "creator_last_name"
            ),
            "creator_orcid": config_dict[ConfigKeys.RUI_LOCATION_KEY].get(
                "creator_orcid"
            ),
            "creation_date": today,
            "x_dimension": rui.get("x_dimension"),
            "y_dimension": rui.get("y_dimension"),
            "z_dimension": rui.get("z_dimension"),
            "dimension_units": rui.get("dimension_units", "millimeter"),
            "placement": rui.get(ConfigKeys.PLACEMENT, {}),
            "ccf_annotations": rui.get("ccf_annotations", []),
        }

        entities.append(entity)
    with open(output_path, "w") as f:
        json.dump(entities, f, indent=2)

    print(f"\n JSON-LD written to: {output_path}")

def generate_dataset_graph_jsonld_from_blocks(
    blocks, context, config_dict, source_graph, output_path
):

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
            "@id": block.metadata.get("donor"),
            "@type": block.metadata.get("@type"),
            "label": str(donor_obj.get(ConfigKeys.LABEL, "")),
            "description": donor_obj.get("description", ""),
            "link": block.metadata.get(ConfigKeys.LINK),
            "consortium_name": donor_obj.get("consortium_name"),
            "provider_name": donor_obj.get("provider_name"),
            "provider_uuid": donor_obj.get("provider_uuid"),
            "sex": donor_obj.get(ConfigKeys.SEX),
            "samples": [],
        }

        rui = sample.get(ConfigKeys.RUI_LOCATION_KEY, {})

        spatial_entity = {
            "@context": context,
            "@id": block.metadata.get(ConfigKeys.AT_ID),
            "@type": "SpatialEntity",
            "label": sample.get("@id"),
            "creator": config_dict[ConfigKeys.RUI_LOCATION_KEY].get("creator"),
            "creator_first_name": config_dict[ConfigKeys.RUI_LOCATION_KEY].get(
                "creator_first_name"
            ),
            "creator_last_name": config_dict[ConfigKeys.RUI_LOCATION_KEY].get(
                "creator_last_name"
            ),
            "creator_orcid": config_dict[ConfigKeys.RUI_LOCATION_KEY].get(
                "creator_orcid"
            ),
            "creation_date": today,
            "x_dimension": rui.get("x_dimension"),
            "y_dimension": rui.get("y_dimension"),
            "z_dimension": rui.get("z_dimension"),
            "dimension_units": rui.get("dimension_units", "millimeter"),
            "placement": rui.get(ConfigKeys.PLACEMENT, {}),
            "ccf_annotations": rui.get("ccf_annotations", []),
        }

        sample_entry = {
            "@id": sample.get(ConfigKeys.AT_ID),
            "@type": sample.get("@type"),
            "sample_type": sample.get("sample_type", "Tissue Block"),
            "label": sample.get(ConfigKeys.LABEL, ""),
            "description": sample.get("description"),
            "link": sample.get(ConfigKeys.LINK),
            "section_count": sample.get("section_count", 0),
            "section_size": sample.get("section_size", 0),
            ConfigKeys.RUI_LOCATION_KEY: spatial_entity,
        }

        millitome_donor["samples"].append(sample_entry)

        millitome_graph.append(millitome_donor)

    dataset_graph = {"@context": context, "@graph": millitome_graph}

    with open(output_path, "w") as f:
        json.dump(dataset_graph, f, indent=2)

def get_rotation_matrix(axis: str, angle_deg: float):
    angle_rad = np.radians(angle_deg)

    if axis == "x":
        return trimesh.transformations.rotation_matrix(angle_rad, [1, 0, 0])
    elif axis == "y":
        return trimesh.transformations.rotation_matrix(angle_rad, [0, 1, 0])
    elif axis == "z":
        return trimesh.transformations.rotation_matrix(angle_rad, [0, 0, 1])
    else:
        raise ValueError("Axis must be 'x', 'y', or 'z'")