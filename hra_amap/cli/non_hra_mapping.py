import sys
from hra_amap.registration.organ import Organ
from hra_amap.registration.tissue import TissueBlock
from hra_amap.registration.pipeline import Pipeline
from hra_amap.registration.dataclass import Projection
from hra_amap.utils.conversions import to_pointcloud
from hra_amap.utils.metrics import get_translations

import hra_api_client
from hra_api_client.api import v1_api
from hra_amap.utils.io import read_yaml
from hra_amap.utils.constants import ConfigKeys
from hra_amap.utils.non_hra_mapping import (
    build_block_metadata,
    scale_millitome_block,
    generate_extraction_sites_jsonld_from_blocks,
    generate_dataset_graph_jsonld_from_blocks,
)
from hra_amap.cli.registration_stage_2 import (
    ProjectionBlockGenerator,
)

import time
import trimesh
import numpy as np
from copy import deepcopy
from tqdm.auto import tqdm
from pathlib import Path
import requests
import json

reddishpink = np.array([222, 49, 99, 100], dtype=np.uint8)

class NonHRAMapping:
    """
    Orchestrates the Non-HRA mapping pipeline.
    """

    def __init__(
        self,
        stage1_projection: Path,
        config_path: Path,
        output_dir: Path,
    ):
        self.stage1_projection = stage1_projection
        self.config_path = config_path
        self.output_dir = output_dir

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize HRA API client
        configuration = hra_api_client.Configuration(
            host="https://apps.humanatlas.io/api"
        )
        api_client = hra_api_client.ApiClient(configuration)
        self.api_instance = v1_api.V1Api(api_client)

    def load_config(self):
        """
        Load the YAML configuration file and resolve the source model path
        relative to the config file location.
        """
        self.config_dict = read_yaml(self.config_path)
        self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE] = (
            self.config_path.parent
            / self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]
        )
        self.source_path = self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]
        self.source_model = self.fuse_mesh(trimesh.load(self.source_path))
    
    def fuse_mesh(self, scene_or_mesh):
        if isinstance(scene_or_mesh, trimesh.Scene):
            fused_mesh = trimesh.util.concatenate(scene_or_mesh.dump())
        else:
            fused_mesh = scene_or_mesh
        return fused_mesh

    def fetch_and_filter(self):
        """
        Fetch donor graph data from the HRA API and filter samples based on organ, sex, and ontology term.
        Args:
            result: Database readiness result (unused, but ensures sequencing)
        Returns:
            Filtered donor sample graph.
        """
        try:
            # Query donor graph using ontology term
            url = "https://apps.humanatlas.io/api/v1/ds-graph"
            donar_sex = self.config_dict[ConfigKeys.DONOR_DATA_KEY][ConfigKeys.SEX]
            ontology_term = self.config_dict[ConfigKeys.DONOR_DATA_KEY][ConfigKeys.SELECTED_ORGAN]
            params = {
                "ontology-terms": ontology_term,
                "sex": donar_sex
            }

            response = requests.get(url, params=params)
            self.data = response.json()

            filter_result = self.data.get(ConfigKeys.AT_GRAPH, [])
            return filter_result

        except hra_api_client.ApiException as e:
            print("Exception when calling DefaultApi->aggregate_results: %s\n" % e)

    def load_projection_block(self):
        """
        Load projected tissue blocks generated from Stage-1 registration
        and compute oriented bounding boxes for visualization.
        """
        # Generate projected blocks from Stage-1 projection
        self.projected_blocks = ProjectionBlockGenerator(
            self.stage1_projection, self.config_path
        ).generate_projections()

        # Extract oriented bounding boxes for each block
        self.projected_blocks_obb = {
            id: block.bounding_box_oriented
            for id, block in deepcopy(self.projected_blocks).items()
        }

        for index, obb in self.projected_blocks_obb.items():
            obb.visual.vertex_colors = self.projected_blocks[
                index
            ].visual.vertex_colors[0]
   
    def build_model(self, result):
        """
        Build the final 3D scene by mapping donor blocks into the
        source organ model space and exporting a GLB.
        """

        self.blocks = []
        target_name = self.config_dict[ConfigKeys.TARGET_NAME]
        translation_list = get_translations(
            target_name=self.config_dict[ConfigKeys.TARGET_NAME]
        )
        remove_block = self.config_dict.get("remove-block", [])

        for donor in result:
            for sample in donor['samples']:

                placement = sample.get("rui_location", {}).get("placement", {})

                if "Patch" in placement.get("target", ""):
                    continue

                block = TissueBlock.from_sample(sample, donor, target_name, translation_list)
                value = sample.get("@id", None)
                if not value in remove_block :
                    result = value.split("#")[-1] if value and "#" in value else None
                    block.id = block.label = result
                    block.metadata = build_block_metadata(sample, donor)
                    self.blocks.append(block)

        projection = Projection.load(self.stage1_projection)

        projected_blocks = []
        for block in self.blocks:
            projected = projection.project(deepcopy(block))

            projected.metadata = block.metadata.copy()
            projected.id = block.id
            projected.label = block.label

            projected_blocks.append(projected)

        bounding_blocks = []

        for block in projected_blocks:
            bbox = block.bounding_box_oriented

            bbox.metadata = block.metadata.copy()
            bbox.id = block.id
            bbox.label = block.label

            sample = bbox.metadata.get("sample", {})
            rui = sample.get(ConfigKeys.RUI_LOCATION_KEY, {})
            placement = rui.get(ConfigKeys.PLACEMENT, {})

            placement["x_translation"] = float(bbox.centroid[0])
            placement["y_translation"] = float(bbox.centroid[1])
            placement["z_translation"] = float(bbox.centroid[2])

            bbox.metadata["centroid"] = bbox.centroid.tolist()

            bounding_blocks.append(bbox)

        self.source_model.visual = trimesh.visual.ColorVisuals(
            mesh=self.source_model,
            vertex_colors=np.tile(reddishpink, (self.source_model.vertices.shape[0], 1))
        )

        self.blocks = bounding_blocks
        scene = trimesh.scene.Scene([bounding_blocks, self.source_model])
        scene.export(self.output_dir / "non_hra_mapping.glb")

    def export_json(self):
        """
        Export JSON-LD outputs describing extraction sites
        and dataset graph metadata.
        """
        generate_extraction_sites_jsonld_from_blocks(
            self.blocks,
            self.data[ConfigKeys.AT_CONTEXT],
            self.config_dict,
            output_path=self.output_dir / "extraction-sites.jsonld",
        )

        generate_dataset_graph_jsonld_from_blocks(
            self.blocks,
            self.data[ConfigKeys.AT_CONTEXT],
            self.config_dict,
            self.data[ConfigKeys.AT_GRAPH],
            output_path=self.output_dir / "dataset-graph.jsonld",
        )

    def run(self):
        """
        Execute the full Non-HRA mapping pipeline end-to-end.
        """
        self.load_config()
        filter_result = self.fetch_and_filter()
        self.build_model(filter_result)
        self.export_json()
        print("Complete")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Non-HRA Mapping")
    parser.add_argument("--stage1_projection_path", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output_path", type=Path, required=True)

    args = parser.parse_args()

    mapping = NonHRAMapping(
        stage1_projection=args.stage1_projection_path,
        config_path=args.config,
        output_dir=args.output_path,
    )

    mapping.run()

if __name__ == "__main__":
    main()
