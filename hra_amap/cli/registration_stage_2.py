"""
Stage 2 of Millitome Registrations: Generates tissue blocks from projections and outputs JSON-LD files.
"""

import argparse
from copy import deepcopy
from datetime import datetime
from hra_amap.utils.constants import ConfigKeys
import json
import yaml
import trimesh  # type: ignore
import requests
import csv
import io
import numpy as np

from pathlib import Path
from tqdm.auto import tqdm
from hra_amap.registration.tissue import TissueBlock
from hra_amap.registration.dataclass import Projection
from hra_amap.registration.rui import RUIProcessor
from hra_amap.utils.io import read_yaml
from hra_amap.utils.metrics import get_translations


class TissueBlockGenerator:
    """
    Generates TissueBlock objects from Millitome mesh and configuration.
    """

    def __init__(self, config: Path):
        self.config = config
        self.config_dict = {}
        self.tissue_blocks = []

    def update_id_label_date(self, label):
        """
        Update IDs, labels, and creation dates based on tissue block label.
        """
        donor_id = self.config_dict[ConfigKeys.DONOR_DATA_KEY][ConfigKeys.ID]
        self.config_dict[ConfigKeys.RUI_LOCATION_KEY][
            ConfigKeys.AT_ID
        ] = f"{donor_id}#{label}"
        self.config_dict[ConfigKeys.RUI_LOCATION_KEY][ConfigKeys.PLACEMENT][
            ConfigKeys.AT_ID
        ] = f"{donor_id}#{label}_placement"

        self.config_dict[ConfigKeys.DONOR_DATA_KEY][ConfigKeys.LABEL] = label
        self.config_dict[ConfigKeys.RUI_LOCATION_KEY][ConfigKeys.LABEL] = label

        date_today = datetime.today().strftime("%Y-%m-%d")
        self.config_dict[ConfigKeys.RUI_LOCATION_KEY][
            ConfigKeys.CREATION_DATE
        ] = date_today
        self.config_dict[ConfigKeys.RUI_LOCATION_KEY][ConfigKeys.PLACEMENT][
            ConfigKeys.PLACEMENT_DATE
        ] = date_today

    def update_config_values(self):
        """
        Resolve relative paths and update config values.
        """
        # Update input file path relative to config
        self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE] = (
            self.config.parent
            / self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]
        )
        self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET] = (
            self.config.parent
            / self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET]
        )
        # update donar data link values
        self.config_dict[ConfigKeys.DONOR_DATA_KEY][ConfigKeys.LINK] = self.config_dict[
            ConfigKeys.DONOR_DATA_KEY
        ][ConfigKeys.ID]

    def generate_blocks(self):
        """
        Generate all tissue blocks from millitome data.
        """
        self.config_dict = read_yaml(self.config)
        self.update_config_values()
        millitome = trimesh.load(
            Path(self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE])
        )
        translation_list = get_translations(
            target_name=self.config_dict[ConfigKeys.TARGET_NAME]
        )

        fused_labels = set()
        fused_block_config = self.config_dict.get("fused-blocks", {})

        if fused_block_config:
            for fused_label, fused_block_ids in fused_block_config.items():
                fused_labels.update(str(id) for id in fused_block_ids)

                self.update_id_label_date(fused_label)
                try:
                    merged_mesh = trimesh.util.concatenate(
                        [
                            millitome.geometry[str(block_id)]
                            for block_id in fused_block_ids
                        ]
                    )
                except KeyError as e:
                    raise ValueError(
                        f"Block ID '{e.args[0]}' in fused-blocks '{fused_label}' does not exist"
                    )
                fused_tissue_block = TissueBlock.from_millitome(
                    merged_mesh,
                    donor=self.config_dict[ConfigKeys.DONOR_DATA_KEY],
                    metadata=self.config_dict[ConfigKeys.RUI_LOCATION_KEY],
                    translation_arr=translation_list,
                    label=fused_label,
                )
                self.tissue_blocks.append(fused_tissue_block)

        for label, block in millitome.geometry.items():
            self.update_id_label_date(label)
            tissue_block = TissueBlock.from_millitome(
                block,
                donor=self.config_dict[ConfigKeys.DONOR_DATA_KEY],
                metadata=self.config_dict[ConfigKeys.RUI_LOCATION_KEY],
                translation_arr=translation_list,
                label=label,
            )
            self.tissue_blocks.append(tissue_block)

        for tissue_block in self.tissue_blocks:
            tissue_block.visual.vertex_colors = trimesh.visual.random_color()

        return self.tissue_blocks


class ProjectionBlockGenerator:
    """
    Projects tissue blocks using the loaded projection model.
    """

    def __init__(self, projection: Path, config: Path):
        self.projection = Projection.load(projection)
        self.tissue_blocks = TissueBlockGenerator(config).generate_blocks()

    def generate_projections(self):
        """
        Apply projection and AABB bounding box generation to each tissue block.
        """
        projected_blocks = [
            self.projection.project(block) for block in self.tissue_blocks
        ]
        projected_blocks_aabb = [
            block.bounding_box for block in deepcopy(projected_blocks)
        ]

        # Ensure colors match for bounding boxes
        for index, aabb in enumerate(projected_blocks_aabb):
            aabb.visual.vertex_colors = projected_blocks[index].visual.vertex_colors[0]

        return projected_blocks


def generate_output(projection: Path, output_dir: Path, config: Path):
    """
    Main workflow to generate projection output files.
    """

    projected_blocks = ProjectionBlockGenerator(
        projection, config
    ).generate_projections()
    processor = RUIProcessor(blocks=projected_blocks, registration_dir=output_dir)
    processor.initialize_registration()
    processor.generate_rui_locations(config)

    with open(output_dir / "rui_locations.jsonld", "r") as f:
        jsonld = json.load(f)

    # Extract the rui_locations
    extraction_sites = [
        sample["rui_location"]
        for donor in jsonld["@graph"]
        for sample in donor["samples"]
    ]

    with open(output_dir / "dataset-graph.jsonld", "w") as f:
        json.dump(jsonld, f, indent=2)

    # Create extraction-sites.jsonld
    with open(output_dir / "extraction-sites.jsonld", "w") as f:
        json.dump(extraction_sites, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Millitome Registrations stage 2")
    parser.add_argument(
        "--stage1_projection_path",
        type=Path,
        required=True,
        help="Path where stage 1 output was saved",
    )
    parser.add_argument(
        "--output_path", type=Path, required=True, help="Path to store the results"
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="rui location and donor data config file",
    )

    args = parser.parse_args()

    try:
        generate_output(args.stage1_projection_path, args.output_path, args.config)
    except Exception as e:
        print(e)
        raise e


if __name__ == "__main__":
    main()
