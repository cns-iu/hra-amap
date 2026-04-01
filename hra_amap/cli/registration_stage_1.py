"""
Stage 1 of Millitome Registrations: Module to perform projection generation using organ registration pipeline.
"""

import argparse
import yaml
import trimesh
import numpy as np
import requests
from pathlib import Path
from hra_amap.registration.organ import Organ
from hra_amap.registration.pipeline import Pipeline
from hra_amap.utils.io import read_yaml, write_yaml
from hra_amap.utils.constants import ConfigKeys
from hra_amap.utils.preprocess import download_and_process_glb_file

class ProjectionPickle:
    """
    Handles loading configuration and generating organ projections.
    Supports optional siibra-driven source mesh generation when configured.
    """

    def generate_source_from_siibra_if_configured(self):
        """
        If `siibra` section exists in config, fetch the configured template mesh
        and export it to input_files.source.
        """
        siibra_cfg = self.config_dict.get("siibra")
        if not siibra_cfg:
            return

        atlas_name = siibra_cfg.get("atlases")
        template_space = siibra_cfg.get("template_space")
        if not atlas_name or not template_space:
            raise ValueError(
                "Config key 'siibra' must include both 'atlases' and 'template_space'."
            )

        try:
            import siibra
        except ImportError as exc:
            raise ImportError(
                "siibra is required when config contains a 'siibra' section. "
                "Install it in your environment and retry."
            ) from exc

        template = siibra.atlases.get(atlas_name).get_template(space=template_space)
        if not template.provides_mesh:
            raise ValueError(
                f"Template '{template_space}' in atlas '{atlas_name}' does not provide a mesh."
            )

        template_mesh = template.fetch(format="mesh")
        mesh = trimesh.Trimesh(
            vertices=np.array(template_mesh["verts"]),
            faces=np.array(template_mesh["faces"]),
            process=False,
        )

        source_path = Path(self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE])
        source_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(source_path)

    def load_registration_data(self):
        """
        Load configuration and update input file paths.
        """
        self.config_dict = read_yaml(self.config)
        self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE] = (
            self.config.parent
            / self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]
        )

        self.generate_source_from_siibra_if_configured()

        target = requests.get(
            self.config_dict[ConfigKeys.TARGET_NAME],
            headers={"Accept": "application/json"},
        ).json()
        glb_url = target["data"][0]["object_reference"]["file_url"]

        raw_data_dir = (
            Path("raw-data")
            / "millitome"
            / self.config.parent.parent.name
            / self.config.parent.name
        )
        if self.backward_projection:
            raw_data_dir = Path("raw-data") / "external-atlas" / self.config.parent.name
        retain = self.config_dict.get(ConfigKeys.RETAIN_COMPONENT)
        glb_path = download_and_process_glb_file(glb_url, raw_data_dir, retain)
        if glb_path:
            self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET] = glb_path

    def __init__(self, config: Path, backward_projection: bool):
        """
        Initialize with configuration path.
        """
        self.config = config
        self.backward_projection = backward_projection
        self.load_registration_data()

    def generate_projection(
        self,
        output_path: Path,
        point_cloud_output: Path,
        pipeline_name: str,
        pipeline_discription: str,
    ):
        """
        Generate projection data and export it to the given path.
        """
        source_path = self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]
        target_path = self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET]

        if not source_path.exists():
            raise FileNotFoundError(f"Source path not found: {source_path}")

        if not target_path.exists():
            raise FileNotFoundError(f"Target path not found: {target_path}")

        if self.backward_projection:
            source_path, target_path = target_path, source_path

        source = Organ(
            path=source_path,
            target_name=self.config_dict[ConfigKeys.TARGET_NAME],
        )

        target = Organ(
            path=target_path,
            target_name=self.config_dict[ConfigKeys.TARGET_NAME],
        )

        pipeline = Pipeline(
            name=pipeline_name, description=pipeline_discription, params=self.config
        )

        projections = pipeline.run(source=source, target=target)
        projections.export(path=str(output_path))

        projected_pc = trimesh.PointCloud(
            projections.registration.vertices,
            colors=np.tile(
                np.array([255, 0, 0, 1]), (len(projections.registration.vertices), 1)
            ),
        )
        hra_pc = trimesh.PointCloud(
            target.vertices,
            colors=np.tile(np.array([0, 0, 255, 1]), (len(target.vertices), 1)),
        )
        after_scene = trimesh.Scene([projected_pc, hra_pc])
        output_file = point_cloud_output / "point_cloud_transformation_fit.glb"
        after_scene.export(str(output_file))


def main():
    parser = argparse.ArgumentParser(description="Millitome Registrations stage 1")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="rui location and donor data config file",
    )
    parser.add_argument(
        "--output_path",
        type=Path,
        required=True,
        help="path to store projections pickle file",
    )
    parser.add_argument(
        "--point_cloud_output_path",
        type=Path,
        required=True,
        help="path to store the point cloud transformation glb",
    )
    parser.add_argument(
        "--pipeline_name",
        type=str,
        required=False,
        help="Name of pipeline",
        default="millitome_projections",
    )
    parser.add_argument(
        "--pipeline_discription",
        type=str,
        required=False,
        help="Discription of pipeline",
        default="HRA Millitome Projection Pipeline",
    )
    parser.add_argument(
        "--backward_projection",
        action="store_true",
        help="Backward projection from HRA to non-HRA",
    )

    args = parser.parse_args()

    try:
        ProjectionPickle(args.config, args.backward_projection).generate_projection(
            args.output_path,
            args.point_cloud_output_path,
            args.pipeline_name,
            args.pipeline_discription,
        )
    except Exception as e:
        raise


if __name__ == "__main__":
    main()
