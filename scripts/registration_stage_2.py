import argparse
from copy import deepcopy
from datetime import datetime
import json
import uuid
import yaml
import random
import trimesh # type: ignore
from pathlib import Path
from tqdm.auto import tqdm
from hra_amap.registration.tissue import TissueBlock
from hra_amap.registration.dataclass import Projection
from hra_amap.registration.rui import RUIProcessor


rd = random.Random()
rd.seed(12)


class TissueBlockGenerator:
    donor_data_key = 'Donor Data'
    rui_location_key ='RUI Location'
    def __init__(self, source: Path, target_name : str, registration_data_path : Path):
        self.source = source
        self.target_name = target_name
        self.registration_data_path = registration_data_path
        self.registration_dict = {}
        self.tissue_blocks = []
    
    def load_registration_data(self):
        with open(self.registration_data_path, "r") as file:
            self.registration_dict = yaml.safe_load(file)

    def update_id_label_date(self, label):
        donor_id = self.registration_dict[self.donor_data_key]['id']
        self.registration_dict[self.rui_location_key]['@id'] = f"{donor_id}#{label}"
        self.registration_dict[self.rui_location_key]['placement']['@id'] =  f"{donor_id}#{label}_placement"

        self.registration_dict[self.donor_data_key]['label'] = label
        self.registration_dict[self.rui_location_key]['label'] = label
        
        date_today = datetime.today().strftime('%Y-%m-%d')
        self.registration_dict[self.rui_location_key]['creation_date'] = date_today
        self.registration_dict[self.rui_location_key]['placement']['placement_date'] = date_today

    def generate_blocks(self):
        self.load_registration_data()
        millitome = trimesh.load(self.source)
        for label, block in millitome.geometry.items():
            self.update_id_label_date(label)
            tissue_block = TissueBlock.from_millitome(
                block, donor=self.registration_dict[self.donor_data_key], metadata=self.registration_dict[self.rui_location_key],
                target_name=self.target_name, label=label
            )
            self.tissue_blocks.append(tissue_block)

        for tissue_block in self.tissue_blocks:
            tissue_block.visual.vertex_colors = trimesh.visual.random_color()

        return self.tissue_blocks

class ProjectionBlockGenerator:
    def __init__(self, source: Path, projection: Path, target_name: str, registration_data_path : Path):
        self.source = source
        self.projection = Projection.load(projection)
        self.tissue_blocks = TissueBlockGenerator(source, target_name, registration_data_path).generate_blocks()

    def generate_projections(self):
        projected_blocks = [self.projection.project(block) for block in self.tissue_blocks]
        projected_blocks_aabb = [block.bounding_box for block in deepcopy(projected_blocks)]

        # Ensure colors match for bounding boxes
        for index, aabb in enumerate(projected_blocks_aabb):
            aabb.visual.vertex_colors = projected_blocks[index].visual.vertex_colors[0]

        return projected_blocks

def generate_output(source: Path, projection: Path, output_dir: Path, target_name : str, registration_data_path : Path):
    projected_blocks = ProjectionBlockGenerator(source, projection, target_name, registration_data_path).generate_projections()
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
    parser.add_argument('--source_path', type=Path, required=True, help="Path to source organ file")
    parser.add_argument("--stage1_projection_path", type=Path, required=True, help="Path where stage 1 output was saved")
    parser.add_argument("--output_path", type=Path, required=True, help="Path to store the results")
    parser.add_argument('--target_name', type=str,required=True, help="rui target name as given in atlas_paths.yaml")
    parser.add_argument('--registration_data_path', type = Path, required= True, help="rui location and donor data config file")

    args = parser.parse_args()

    try:
        generate_output(args.source_path, args.stage1_projection_path, args.output_path, args.target_name, args.registration_data_path)
    except Exception as e:
        print(e)
        raise e


# python -m scripts.registration_stage_2 \
#      --source_path input-data/millitome/pancreas-female-vu/v.0.0.1/source/generic-pancreas-organ.glb \
#      --stage1_projection_path raw-data/millitome/pancreas-female-vu/v.0.0.1/projections.pickle \
#      --output_path output-data/millitome/pancreas-female-vu/v.0.0.1 \
#      --target_name VHFPancreas \
#      --registration_data_path configs/millitome/pancreas-female-vu/v.0.0.1/registration_data.yaml