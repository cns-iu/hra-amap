import argparse
from pathlib import Path
from hra_amap.registration.organ import Organ
from hra_amap.registration.pipeline import Pipeline
from hra_amap.utils.io import read_yaml
from scripts.constants import ConfigKeys


REGISTRATION_CONFIG =  {
    "pipeline_name" : "millitome_projections",
    "description" : "HRA Millitome Projection Pipeline",
    "params" : Path('configs/params.yaml'),
}
class ProjectionPickle:
    def load_registration_data(self):
        self.config_dict = read_yaml(self.config)
        self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE] = self.config.parent / self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]
        self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET] = self.config.parent / self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET]
        
    def __init__(self, config : Path):
        self.config = config
        self.load_registration_data()

    def generate_projection(self, output_path: Path, param_config_path: Path, pipeline_name: str, pipeline_discription:str):
        if not self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE].exists():
            raise FileNotFoundError(f"Source path not found: {self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE]}")
        if not self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET].exists():
            raise FileNotFoundError(f"Target path not found: {self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET]}")

        source = Organ(path=self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.SOURCE], target_name = self.config_dict[ConfigKeys.TARGET_NAME])
        target = Organ(path=self.config_dict[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET], target_name= self.config_dict[ConfigKeys.TARGET_NAME])

        pipeline = Pipeline( 
            name= pipeline_name,
            description= pipeline_discription,
            params=param_config_path
        )

        projections = pipeline.run(source=source, target=target)
        projections.export(path=str(output_path))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Millitome Registrations stage 1')
    parser.add_argument('--config', type = Path, required= True, help="rui location and donor data config file")
    parser.add_argument('--output_path',type=Path, required= True, help="path to store projections pickle file")
    parser.add_argument('--params_config_path', type=Path, required=False, help="Path to non rigid registration config file", default = REGISTRATION_CONFIG["params"])
    parser.add_argument('--pipeline_name', type=str, required=False, help="Name of pipeline", default = REGISTRATION_CONFIG["pipeline_name"])
    parser.add_argument('--pipeline_discription', type=str, required=False,help="Discription of pipeline", default= REGISTRATION_CONFIG["description"])
    
    args = parser.parse_args()

    try:
        ProjectionPickle(args.config).generate_projection( args.output_path, args.params_config_path, args.pipeline_name, args.pipeline_discription)
    except Exception as e:
        raise


# python -m scripts.registration_stage_1 \
#     --config input-data/millitome/pancreas-female-vu/v1.0/config.yaml \
#     --output_path raw-data/millitome/pancreas-female-vu/v1.0