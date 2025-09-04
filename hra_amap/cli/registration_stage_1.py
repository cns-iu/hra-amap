"""
Stage 1 of Millitome Registrations: Module to perform projection generation using organ registration pipeline.
"""

import argparse
import yaml
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
    """

    def load_registration_data(self):
        """
        Load configuration and update input file paths.
        """

    def load_registration_data(self):
        self.config_dict = read_yaml(self.config)
        self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE] = (
            self.config.parent
            / self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]
        )

        target = requests.get(self.config_dict[ConfigKeys.TARGET_NAME], headers={"Accept": "application/json"}).json()
        glb_url = target['data'][0]['object_reference']['file_url']

        raw_data_dir = Path("raw-data") / "millitome" / self.config.parent.parent.name / self.config.parent.name
        retain = self.config_dict.get(ConfigKeys.RETAIN_COMPONENT)
        glb_path = download_and_process_glb_file(glb_url, raw_data_dir, retain)
        if glb_path:
            self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET] = glb_path

    def __init__(self, config: Path):
        """
        Initialize with configuration path.
        """
        self.config = config
        self.load_registration_data()

    def generate_projection(
        self, output_path: Path, pipeline_name: str, pipeline_discription: str
    ):
        """
        Generate projection data and export it to the given path.
        """
        if not self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE].exists():
            raise FileNotFoundError(
                f"Source path not found: {self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]}"
            )
        if not self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET].exists():
            raise FileNotFoundError(
                f"Target path not found: {self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET]}"
            )

        target_path = self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET]

        source = Organ(
            path=self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE],
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

    args = parser.parse_args()

    try:
        ProjectionPickle(args.config).generate_projection(
            args.output_path, args.pipeline_name, args.pipeline_discription
        )
    except Exception as e:
        raise


if __name__ == "__main__":
    main()
