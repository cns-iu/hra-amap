import argparse
from pathlib import Path
from src.registration.organ import Organ
from src.registration.pipeline import Pipeline

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

def generate_projection(source_path: Path, target_path: Path):
    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Target path not found: {target_path}")

    source = Organ(path=source_path, mapping_path = REGISTRATION_CONFIG["mapping_config"], transform_path = REGISTRATION_CONFIG["transform_config"])
    target = Organ(path=target_path, mapping_path = REGISTRATION_CONFIG["mapping_config"], transform_path = REGISTRATION_CONFIG["transform_config"])

    pipeline = Pipeline( 
        name= REGISTRATION_CONFIG["pipeline_name"],
        description= REGISTRATION_CONFIG["description"],
        params=REGISTRATION_CONFIG["params"]
    )
    
    projection_dir, folder_name = get_projection_dir(source_path)

    projections = pipeline.run(source=source, target=target)
    projections.export(path=str(projection_dir), folder_name= folder_name)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Millitome Registrations stage 1')
    parser.add_argument('--source_path', type=Path, required=True, help="Path to source organ file")
    parser.add_argument('--target_path', type=Path, required=True, help="Path to target organ file")
    
    args = parser.parse_args()

    try:
        generate_projection(args.source_path, args.target_path)
    except Exception as e:
        raise
