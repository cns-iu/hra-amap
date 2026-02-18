import sys
from hra_amap.registration.organ import Organ
from hra_amap.registration.tissue import TissueBlock
from hra_amap.registration.pipeline import Pipeline
from hra_amap.registration.dataclass import Projection
from hra_amap.utils.conversions import to_pointcloud

import hra_api_client
from hra_api_client.api import v1_api
from hra_amap.utils.io import read_yaml
from hra_amap.utils.constants import ConfigKeys
from hra_amap.utils.non_hra_mapping import (
    build_mesh_from_sample,
    scale_millitome_block,
    filter_samples,
    build_blocks_and_donor_points,
    generate_extraction_sites_jsonld_from_blocks,
    generate_dataset_graph_jsonld_from_blocks,
)
from hra_amap.cli.registration_stage_2 import (
    ProjectionBlockGenerator,
    TissueBlockGenerator,
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
        ontology_term: str,
    ):
        self.stage1_projection = stage1_projection
        self.config_path = config_path
        self.output_dir = output_dir
        self.ontology_term = ontology_term

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

    def wait_for_db_ready(self):
        """
        Poll the HRA backend until the database reports a 'Ready' state.

        Returns:
            The final database status response object.
        """
        db_ready = False
        result = None

        # Keep polling until DB reports readiness
        while not db_ready:
            result = self.api_instance.db_status()
            if result.status == "Ready":
                db_ready = True
            else:
                print("Database not ready yet! Retrying...", result)
                time.sleep(2)

        print("Database ready!\n", result)
        return result

    def fetch_and_filter(self, result):
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
            params = {"ontology-terms": self.ontology_term}

            response = requests.get(url, params=params)
            self.data = response.json()

            graph_size = len(self.data.get(ConfigKeys.AT_GRAPH, []))

            # Extract donor sex from config and normalize to API format
            donar_sex = self.config_dict[ConfigKeys.DONOR_DATA_KEY][ConfigKeys.SEX]
            sex = "F" if donar_sex == "Female" else "M"
            organ = {
                "name": self.config_dict[ConfigKeys.NON_HRA_MAPPING][ConfigKeys.ORGAN],
                "sex": sex,
                "version": "All",
            }

            # Filter donor samples using organ metadata
            filter_result = filter_samples(
                deepcopy(self.data[ConfigKeys.AT_GRAPH]), organ
            )
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

        Args:
            result: Filtered donor sample graph.
        """

        # Load source model
        source_path = self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]
        scene_or_mesh = trimesh.load(source_path)

        if isinstance(scene_or_mesh, trimesh.Scene):
            source_model = trimesh.util.concatenate(scene_or_mesh.dump())
        else:
            source_model = scene_or_mesh

        # Normalize and orient source model
        source_model.apply_translation(-source_model.centroid)

        flip_vec = self.config_dict[ConfigKeys.NON_HRA_MAPPING].get(
            ConfigKeys.FLIP, [1, -1, -1]
        )
        if len(flip_vec) != 3:
            raise ValueError("non_hra_mapping.flip must be length 3")

        flip = np.diag([flip_vec[0], flip_vec[1], flip_vec[2], 1.0])

        x, y, z  = self.config_dict[ConfigKeys.NON_HRA_MAPPING][ConfigKeys.ROTATION]
        angle_rad_x = np.deg2rad(x)
        angle_rad_y = np.deg2rad(y)
        angle_rad_z = np.deg2rad(z)
        rot = trimesh.transformations.euler_matrix(angle_rad_x, angle_rad_y, angle_rad_z, axes="sxyz")

        source_model.apply_transform(flip)
        source_model.apply_transform(rot)
        source_model.invert()
        source_model.fix_normals()

        # Compute source bounds and scaling
        source_min, source_max = source_model.bounds
        source_range = source_max - source_min
        scaling_factor = np.mean(source_range) / 0.1

        # Build blocks and donor points
        self.blocks, donor_points = build_blocks_and_donor_points(
            result, scaling_factor
        )

        # Compute donor bounds
        donor_min = donor_points.min(axis=0)
        donor_max = donor_points.max(axis=0)
        donor_range = np.where(donor_max - donor_min == 0, 1.0, donor_max - donor_min)

        # Compute per-axis scaling
        scale_per_axis = source_range / donor_range

        # Map blocks into source model space
        for block, donor_center in zip(self.blocks, donor_points):
            mapped = source_min + (donor_center - donor_min) * scale_per_axis
            block.apply_translation(mapped - block.centroid)

        # Uniformly scale all blocks
        scale_millitome_block(
            self.blocks,
            self.config_dict[ConfigKeys.NON_HRA_MAPPING][ConfigKeys.MODEL_SCALE],
        )
        source_model.visual = trimesh.visual.ColorVisuals(
            mesh=source_model,
            vertex_colors=np.tile(reddishpink, (source_model.vertices.shape[0], 1)),
        )

        # Build scene
        scene = trimesh.Scene()
        scene.add_geometry(
            source_model, node_name="source_model", geom_name="source_model"
        )

        for i, block in enumerate(self.blocks):
            label = block.metadata.get(ConfigKeys.ID, f"block_{i}")

            scene.add_geometry(block, node_name=label, geom_name=label)
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
        result = self.wait_for_db_ready()
        filter_result = self.fetch_and_filter(result)
        self.load_projection_block()
        self.build_model(filter_result)
        self.export_json()
        print("Complete")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Non-HRA Mapping")
    parser.add_argument("--stage1_projection_path", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output_path", type=Path, required=True)
    parser.add_argument("--ontology-term", type=str, required=True)

    args = parser.parse_args()

    mapping = NonHRAMapping(
        stage1_projection=args.stage1_projection_path,
        config_path=args.config,
        output_dir=args.output_path,
        ontology_term=args.ontology_term,
    )

    mapping.run()


if __name__ == "__main__":
    main()
