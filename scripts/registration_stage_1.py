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


def generate_projection(source_path: Path, target_path: Path, output_path: Path, param_config_path: Path, mapping_config_path: Path, transform_config_path: Path, pipeline_name: str, pipeline_discription:str):
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

    projections = pipeline.run(source=source, target=target)
    projections.export(path=str(output_path))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Millitome Registrations stage 1')
    parser.add_argument('--source_path', type=Path, required=True, help="Path to source organ file")
    parser.add_argument('--target_path', type=Path, required=True, help="Path to target organ file")
    parser.add_argument('--output_path',type=Path, required= True, help="path to store projections pickle file")
    parser.add_argument('--params_config_path', type=Path, required=False, help="Path to non rigid registration config file", default = REGISTRATION_CONFIG["params"])
    parser.add_argument('--atlas_config_path', type=Path, required= False, help="Path to mapping atlas path", default = REGISTRATION_CONFIG["mapping_config"])
    parser.add_argument('--transform_config_path', type=Path, required=False, help="Path to hra transformations", default = REGISTRATION_CONFIG["transform_config"])
    parser.add_argument('--pipeline_name', type=str, required=False, help="Name of pipeline", default = REGISTRATION_CONFIG["pipeline_name"])
    parser.add_argument('--pipeline_discription', type=str, required=False,help="Discription of pipeline", default= REGISTRATION_CONFIG["description"])
    
    args = parser.parse_args()

    try:
        generate_projection(args.source_path, args.target_path, args.output_path, args.params_config_path, args.atlas_config_path, args.transform_config_path, args.pipeline_name, args.pipeline_discription)
    except Exception as e:
        raise


# python -m scripts.registration_stage_1 \
#     --source_path input-data/millitome/pancreas-female-vu/v1.3/source/generic-pancreas-organ.glb \
#     --target_path input-data/millitome/pancreas-female-vu/v1.3/target/3d-vh-f-pancreas.glb\
#     --output_path raw-data/millitome/pancreas-female-vu/v1.3