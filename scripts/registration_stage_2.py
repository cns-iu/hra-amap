import argparse
from copy import deepcopy
from datetime import datetime
import json
import yaml
import trimesh # type: ignore
import requests
import csv
import io
import numpy as np

from pathlib import Path
from tqdm.auto import tqdm
from hra_amap.registration.tissue import TissueBlock
from hra_amap.registration.dataclass import Projection
from hra_amap.registration.rui import RUIProcessor


class TissueBlockGenerator:
    donor_data_key = 'donor'
    rui_location_key ='rui_location'
    input_files = 'input_files'
    source = 'source'
    target = 'target'
    target_name = 'target_name'
    link = 'link'
    id = 'id'
    def __init__(self, config : Path):
        self.config = config
        self.config_dict = {}
        self.tissue_blocks = []
    
    def load_registration_data(self):
        with open(self.config, "r") as file:
            self.config_dict = yaml.safe_load(file)

    def update_id_label_date(self, label):
        donor_id = self.config_dict[self.donor_data_key][self.id]
        self.config_dict[self.rui_location_key]['@id'] = f"{donor_id}#{label}"
        self.config_dict[self.rui_location_key]['placement']['@id'] =  f"{donor_id}#{label}_placement"

        self.config_dict[self.donor_data_key]['label'] = label
        self.config_dict[self.rui_location_key]['label'] = label
        
        date_today = datetime.today().strftime('%Y-%m-%d')
        self.config_dict[self.rui_location_key]['creation_date'] = date_today
        self.config_dict[self.rui_location_key]['placement']['placement_date'] = date_today


    def update_config_values(self):
        # Update input file path relative to config
        self.config_dict[self.input_files][self.source] = self.config.parent / self.config_dict[self.input_files][self.source]
        self.config_dict[self.input_files][self.target] = self.config.parent / self.config_dict[self.input_files][self.target]

        # update donar data link values
        self.config_dict[self.donor_data_key]['link'] = self.config_dict[self.donor_data_key][self.id]
    def generate_blocks(self):
        self.load_registration_data()
        self.update_config_values()
        millitome = trimesh.load(Path(self.config_dict[self.input_files][self.source]))
        translation_list = self.get_translations()
        for label, block in millitome.geometry.items():
            self.update_id_label_date(label)
            tissue_block = TissueBlock.from_millitome(
                block, donor=self.config_dict[self.donor_data_key], metadata=self.config_dict[self.rui_location_key],
                translation_arr = translation_list, label=label
            )
            self.tissue_blocks.append(tissue_block)

        for tissue_block in self.tissue_blocks:
            tissue_block.visual.vertex_colors = trimesh.visual.random_color()

        return self.tissue_blocks
    
    def get_translations(self):
        hra_transforms = self.fetch_anatomical_structure()
        for row in hra_transforms:
            if row[list(row.keys())[0]] == self.config_dict[self.target_name] and row[list(row.keys())[1]] == self.config_dict[self.target_name]:
                return list(row.values())[-3:]
        return None
    
    def fetch_anatomical_structure(self):
        url = "https://grlc.io/api-git/hubmapconsortium/ccf-grlc/subdir/mesh-collision//anatomical-structures"
        params = {
            "endpoint": "https://lod.humanatlas.io/sparql"
        }
        headers = {
            "accept": "text/csv"
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch hra_transforms: {response.status_code}")

        csv_data = list(csv.DictReader(io.StringIO(response.text)))
        return csv_data
    
class ProjectionBlockGenerator:
    def __init__(self, projection: Path, config : Path):
        self.projection = Projection.load(projection)
        self.tissue_blocks = TissueBlockGenerator(config).generate_blocks()

    def generate_projections(self):
        projected_blocks = [self.projection.project(block) for block in self.tissue_blocks]
        projected_blocks_aabb = [block.bounding_box for block in deepcopy(projected_blocks)]

        # Ensure colors match for bounding boxes
        for index, aabb in enumerate(projected_blocks_aabb):
            aabb.visual.vertex_colors = projected_blocks[index].visual.vertex_colors[0]

        return projected_blocks

def generate_output(projection: Path, output_dir: Path,config : Path):
    projected_blocks = ProjectionBlockGenerator(projection, config).generate_projections()
    processor = RUIProcessor(blocks=projected_blocks, registration_dir=output_dir)
    processor.initialize_registration()
    processor.generate_rui_locations()

    with open(output_dir / 'rui_locations.jsonld', 'r') as f:
        jsonld = json.load(f)

    # Extract the rui_locations
    extraction_sites = [sample['rui_location'] for donor in jsonld['@graph'] for sample in donor['samples']]
    
    with open(output_dir / 'dataset-graph.jsonld', 'w') as f:
        json.dump(jsonld, f, indent=2)

    # Create extraction-sites.jsonld
    with open(output_dir / 'extraction-sites.jsonld', 'w') as f:
        json.dump(extraction_sites, f, indent=2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Millitome Registrations stage 2')
    parser.add_argument("--stage1_projection_path", type=Path, required=True, help="Path where stage 1 output was saved")
    parser.add_argument("--output_path", type=Path, required=True, help="Path to store the results")
    parser.add_argument('--config', type = Path, required= True, help="rui location and donor data config file")

    args = parser.parse_args()

    try:
        generate_output(args.stage1_projection_path, args.output_path,args.config)
    except Exception as e:
        print(e)
        raise e


# python -m scripts.registration_stage_2 \
#      --stage1_projection_path raw-data/millitome/pancreas-female-vu/v1.3/projections.pickle \
#      --output_path output-data/millitome/pancreas-female-vu/v1.3 \
#      --config input-data/millitome/pancreas-female-vu/v1.3/config.yaml