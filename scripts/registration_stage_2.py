import argparse
from copy import deepcopy
from datetime import datetime
import json
import uuid
import random
import trimesh # type: ignore
from pathlib import Path
from tqdm.auto import tqdm
from hra_amap.registration.tissue import TissueBlock
from hra_amap.registration.dataclass import Projection
from hra_amap.registration.rui import RUIProcessor


rd = random.Random()
rd.seed(12)
REGISTRATION_DEFAULTS = {
    "donor_data" : Path("data/donor.py"),
    "rui_location" : Path("data/rui_location.py"),
    "target_name" : "VHFPancreas"
}

class TissueBlockGenerator:
    def __init__(self, source: Path, donor_data: Path, rui_location: Path, target_name : str):
        self.source = source
        # self.donor_data = self.load_dict(donor_data)
        # self.rui_location = self.load_dict(rui_location)
        self.target_name = target_name
        self.tissue_blocks = []

    # def load_dict(self, file_path: Path):
        # return runpy.run_path(str(file_path))

    def generate_blocks(self):
        millitome = trimesh.load(self.source)
        for label, block in millitome.geometry.items():
            donor = {'sex': 'Female', 
                    'label': label,
                    'provider_name': 'MC-IU', 
                    'provider_uuid': str(uuid.UUID(int=rd.getrandbits(128), version=4)), 
                    'consortium_name': 'HRA',
                    'id': 'https://purl.humanatlas.io/millitome/generic-ovary-female-right',      # make necessary edits here
                    'link': 'https://purl.humanatlas.io/millitome/generic-ovary-female-right'}        # make necessary edits here

            # create the rui_location data
            rui_location = {'@context': "https://hubmapconsortium.github.io/ccf-ontology/ccf-context.jsonld",
                            '@id': f"{donor['id']}#{label}",
                            '@type': 'SpatialEntity',
                            'creator': 'Bhargav Snehal Desai',      # make necessary edits here
                            'creator_first_name': 'Bhargav Snehal',     # make necessary edits here
                            'creator_last_name': 'Desai',       # make necessary edits here
                            'creator_orcid': 'https://orcid.org/0009-0008-6509-7698',       # make necessary edits here
                            'label': label,
                            'creation_date': datetime.today().strftime('%Y-%m-%d'), 
                            'dimension_units': 'millimeter', 
                            'placement': {'@context': "https://hubmapconsortium.github.io/ccf-ontology/ccf-context.jsonld",
                                        '@id': f"{donor['id']}#{label}_placement", 
                                        '@type': 'SpatialPlacement', 
                                        'target': f'http://purl.org/ccf/latest/ccf.owl#{self.target_name}', 
                                        'placement_date': datetime.today().strftime('%Y-%m-%d'), 
                                        'scaling_units': 'ratio', 
                                        'rotation_order': 'XYZ', 
                                        'rotation_units': 'degree', 
                                        'translation_units': 'millimeter'
                                        }
            }
            tissue_block = TissueBlock.from_millitome(
                block, donor=donor, metadata=rui_location,
                target_name=self.target_name, label=label
            )
            self.tissue_blocks.append(tissue_block)

        for tissue_block in self.tissue_blocks:
            tissue_block.visual.vertex_colors = trimesh.visual.random_color()

        return self.tissue_blocks

class ProjectionBlockGenerator:
    def __init__(self, source: Path, projection: Path, donor_data: Path, rui_location: Path, target_name: str):
        self.source = source
        self.projection = Projection.load(projection)
        self.tissue_blocks = TissueBlockGenerator(source, donor_data, rui_location, target_name).generate_blocks()

    def generate_projections(self):
        projected_blocks = [self.projection.project(block) for block in self.tissue_blocks]
        projected_blocks_aabb = [block.bounding_box for block in deepcopy(projected_blocks)]

        # Ensure colors match for bounding boxes
        for index, aabb in enumerate(projected_blocks_aabb):
            aabb.visual.vertex_colors = projected_blocks[index].visual.vertex_colors[0]

        return projected_blocks

def generate_output(source: Path, projection: Path, output_dir: Path, donor_data: Path, rui_location: Path, target_name : str):
    projected_blocks = ProjectionBlockGenerator(source, projection, donor_data, rui_location, target_name).generate_projections()
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
    parser.add_argument('--donor_data', type=Path, required=False, help="JSON file containing details of the organ donor", default=REGISTRATION_DEFAULTS["donor_data"])
    parser.add_argument('--rui_location', type=Path, required=False, help="JSON file containing details of rui location", default=REGISTRATION_DEFAULTS["rui_location"])
    parser.add_argument('--target_name', type=str,required=False, help="rui target name as given in atlas_paths.yaml",default= REGISTRATION_DEFAULTS["target_name"])

    args = parser.parse_args()

    try:
        generate_output(args.source_path, args.stage1_projection_path, args.output_path, args.donor_data, args.rui_location, args.target_name)
    except Exception as e:
        raise e


# python -m scripts.registration_stage_2 \
#      --source_path input-data/millitome/pancreas-female-vu/v.0.0.1/source/generic-pancreas-organ.glb \
#      --stage1_projection_path raw-data/millitome/pancreas-female-vu/v.0.0.1/projections.pickle \
#      --output_path output-data/millitome/pancreas-female-vu/v.0.0.1