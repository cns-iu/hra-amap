import subprocess

from pathlib import Path
from utils.io import read_yaml, write_yaml, add_header

class RUIProcessor:
    def __init__(self, blocks, registration_dir):
        self.blocks = [blocks] if len(blocks) == 1 else blocks
        self.registration_dir = Path(registration_dir)
    
    def initialize_registration(self):
        subprocess.run(['npx', 'github:hubmapconsortium/hra-rui-locations-processor', 'new', str(self.registration_dir)])
        
        # read YAML
        registrations = read_yaml(self.registration_dir.joinpath('registrations.yaml'))

        # modify attributes
        assert len(set([block.donor['id'] for block in self.blocks])) == 1, "Writing tissue blocks for multiple donors not supported yet"
        registrations[0]['defaults']['id'] = self.blocks[0].donor['id']
        registrations[0]['defaults']['link'] = self.blocks[0].donor['link']
        registrations[0]['consortium_name'] = self.blocks[0].donor['consortium_name']
        registrations[0]['provider_name'] = self.blocks[0].donor['provider_name']
        registrations[0]['provider_uuid'] = self.blocks[0].donor['provider_uuid']
        registrations[0]['donors'][0]['sex'] = self.blocks[0].donor['sex']

        # add names under samples to the registrations yaml
        names = [block.label for block in self.blocks]
        registrations[0]['donors'][0]['samples'] = [{'rui_location': f'{name}.json'} for name in names]

        # write yaml
        write_yaml(self.registration_dir.joinpath('registrations.yaml'), registrations)

        # write header
        add_header(self.registration_dir.joinpath('registrations.yaml'))


    def generate_rui_locations(self):
        # save all the registration data
        assert (self.registration_dir).exists(), "Please initialize a registration object first using initialize_registration"

        # save tissue blocks as jsons
        for block in self.blocks:
            block.to_sample(self.registration_dir.joinpath('registrations'))
        
        # normalize
        subprocess.run(['npx', 'github:hubmapconsortium/hra-rui-locations-processor', 'normalize', '--add-collisions', str(self.registration_dir)])

