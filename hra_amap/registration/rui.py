import subprocess

from bs4 import BeautifulSoup
from pathlib import Path
from hra_amap.utils.io import read_yaml, write_yaml, add_header
from hra_amap.utils.constants import ConfigKeys
import json
from typing import List


class RUIProcessor:
    def __init__(self, blocks, registration_dir):
        """
        Initialize the RUIProcessor with tissue blocks and registration directory.

        Args:
            blocks (list): A list of tissue block objects.
            registration_dir (str): Path to the registration directory.
        """
        self.blocks = [blocks] if len(blocks) == 1 else blocks
        self.registration_dir = Path(registration_dir)

    def initialize_registration(self):
        """
        Initializes the RUI registration by creating necessary files and directories
        using the location processor.
        """
        subprocess.run(
            [
                "npx",
                "github:hubmapconsortium/hra-rui-locations-processor",
                "new",
                str(self.registration_dir),
            ]
        )

        # read YAML
        registrations = read_yaml(self.registration_dir.joinpath("registrations.yaml"))

        # modify attributes
        assert (
            len(set([block.donor["id"] for block in self.blocks])) == 1
        ), "Writing tissue blocks for multiple donors not supported yet"
        registrations[0]["defaults"]["id"] = self.blocks[0].donor["id"]
        registrations[0]["defaults"]["link"] = self.blocks[0].donor["link"]
        registrations[0]["consortium_name"] = self.blocks[0].donor["consortium_name"]
        registrations[0]["provider_name"] = self.blocks[0].donor["provider_name"]
        registrations[0]["provider_uuid"] = self.blocks[0].donor["provider_uuid"]

        donors = []
        for block in self.blocks:
            donors.append(
                {
                    "sex": block.donor["sex"],
                    "label": block.label,
                    "samples": [{"rui_location": f"{block.label}.json"}],
                }
            )

        registrations[0]["donors"] = donors

        # write yaml
        write_yaml(self.registration_dir.joinpath("registrations.yaml"), registrations)

        # write header
        add_header(self.registration_dir.joinpath("registrations.yaml"))

    def generate_rui_locations(self, config: Path):
        """
        Generate the RUI locations after initializing the registration. This involves saving
        the tissue blocks as JSON files and normalizing the data.
        """
        # save all the registration data
        assert (
            self.registration_dir
        ).exists(), "Please initialize a registration object first using initialize_registration"

        # save tissue blocks as jsons
        for block in self.blocks:
            block.to_sample(self.registration_dir.joinpath("registrations"))

        # normalize
        subprocess.run(
            [
                "npx",
                "github:hubmapconsortium/hra-rui-locations-processor",
                "normalize",
                "--add-collisions",
                str(self.registration_dir),
            ]
        )

        self.update_index_html(self.registration_dir / "index.html", config)

    def update_index_html(self, index_path: Path, config_path: Path):
        config = read_yaml(config_path)

        donar_data = config.get(ConfigKeys.DONOR_DATA_KEY, {})
        sex = donar_data.get(ConfigKeys.SEX)
        selected_organ = donar_data.get(ConfigKeys.SELECTED_ORGAN)

        selected_organs = self.get_default_selected_organs()
        if selected_organ and selected_organ not in selected_organs:
            selected_organs.append(selected_organ)

        try:
            with index_path.open("r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
        except FileNotFoundError:
            raise FileNotFoundError(f"Index file not found at: {index_path}")

        # Find <ccf-eui> inside <template id="eui-template">
        template = soup.find("template", id="eui-template")
        if not template:
            raise ValueError("Could not find <template id='eui-template'> in HTML")

        ccf_eui = template.find("ccf-eui")
        if not ccf_eui:
            raise ValueError("Could not find <ccf-eui> inside template")

        ccf_eui["filter"] = json.dumps({ConfigKeys.SEX: sex})
        ccf_eui["selected-organs"] = json.dumps(selected_organs)

        with index_path.open("w", encoding="utf-8") as f:
            f.write(str(soup))

    def get_default_selected_organs(self) -> List[str]:
        return ["http://purl.obolibrary.org/obo/UBERON_0002097"]  # Skin
