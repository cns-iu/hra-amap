import argparse
import yaml
import subprocess
from pathlib import Path
from constants import PathKeys

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def run_command(cmd):
    log.info(f"Running: {' '.join(str(x) for x in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Error:\n{result.stderr}")
        raise RuntimeError(f"Command failed: {' '.join(str(x) for x in cmd)}")

def run_pipeline(config_path: Path):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    for key, millitome in config.items():
        stage1_projection_path = Path(millitome[PathKeys.RAW_DATA_PATH]) / "projections.pickle"

        stage1_cmd = [
            "python", "-m", "scripts.registration_stage_1",
            "--config", millitome[PathKeys.CONFIG_PATH],
            "--output_path", millitome[PathKeys.RAW_DATA_PATH]
        ]
        run_command(stage1_cmd)

        stage2_cmd = [
            "python", "-m", "scripts.registration_stage_2",
            "--stage1_projection_path", str(stage1_projection_path),
            "--output_path", millitome[PathKeys.OUTPUT_PATH],
            "--config", millitome[PathKeys.CONFIG_PATH]
        ]
        run_command(stage2_cmd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Millitome Registration Runner')
    parser.add_argument('--config', type=Path, required=True, help='Path to YAML config with all dataset entries')

    args = parser.parse_args()

    try:
        run_pipeline(args.config)
    except Exception as e:
        print("Pipeline failed:", e)
        raise e


# python scripts/run.py --config scripts/millitome_config.yaml
