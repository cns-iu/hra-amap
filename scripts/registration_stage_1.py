import argparse
from pathlib import Path
from hra_amap.registration.organ import Organ
from hra_amap.registration.pipeline import Pipeline

REGISTRATION_CONFIG =  {
    "pipeline_name" : "millitome_projections",
    "description" : "HRA Millitome Projection Pipeline",
    "params" : Path('configs/params.yaml'),
    "transform_config" : Path('configs/hra_transforms.yaml'),
    "mapping_config" : Path('configs/atlas_paths.yaml')
}
RAW_DATA_DIR = Path("raw_data") 
MILLITOME_DIR = "millitome"

def get_projection_dir(source_path : str):
    path_parts = Path(source_path).parts
    millitome_index = path_parts.index(MILLITOME_DIR)
    folder_name = path_parts[millitome_index + 1]  

    new_dir =  RAW_DATA_DIR / MILLITOME_DIR / folder_name
    if not new_dir.exists():
        try:
            new_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Failed to create directory {new_dir}: {e}")
    return new_dir, folder_name

def generate_projection(source_path: Path, target_path: Path, param_config_path: Path, mapping_config_path: Path, transform_config_path: Path, pipeline_name: str, pipeline_discription:str):
    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Target path not found: {target_path}")

    source = Organ(path=source_path, mapping_path = mapping_config_path, transform_path = transform_config_path)
    target = Organ(path=target_path, mapping_path = mapping_config_path, transform_path = transform_config_path)

    pipeline = Pipeline( 
        name= pipeline_name,
        description= pipeline_discription,
        params=param_config_path
    )
    
    projection_dir, folder_name = get_projection_dir(source_path)

    projections = pipeline.run(source=source, target=target)
    projections.export(path=str(projection_dir), folder_name= folder_name)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Millitome Registrations stage 1')
    parser.add_argument('--source_path', type=Path, required=True, help="Path to source organ file")
    parser.add_argument('--target_path', type=Path, required=True, help="Path to target organ file")
    parser.add_argument('--params_config_path', type=Path, required=False, help="Path to non rigid registration config file", default = REGISTRATION_CONFIG["params"])
    parser.add_argument('--atlas_config_path', type=Path, required= False, help="Path to mapping atlas path", default = REGISTRATION_CONFIG["mapping_config"])
    parser.add_argument('--transform_config_path', type=Path, required=False, help="Path to hra transformations", default = REGISTRATION_CONFIG["transform_config"])
    parser.add_argument('--pipeline_name', type=str, required=False, help="Name of pipeline", default = REGISTRATION_CONFIG["pipeline_name"])
    parser.add_argument('--pipeline_discription', type=str, required=False,help="Discription of pipeline", default= REGISTRATION_CONFIG["description"])
    
    args = parser.parse_args()

    try:
        generate_projection(args.source_path, args.target_path, args.params_config_path, args.atlas_config_path, args.transform_config_path, args.pipeline_name, args.pipeline_discription)
    except Exception as e:
        raise
