"""
Pipeline runner for Millitome tissue registration (stage 1 and 2).
This script traverses all millitome input folders and executes both registration stages.
"""

import subprocess
from pathlib import Path

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


def run_command(cmd, cur_millitome):
    """
    Execute a shell command
    """
    log.info(f"[{cur_millitome}] Running: {' '.join(str(x) for x in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"[{cur_millitome}] Command failed!\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    log.info(result.stdout)


def run_pipeline():
    """
    Main pipeline function to iterate over millitome folders
    and execute stage 1 and 2 registrations.
    """
    base_input = Path("input-data/millitome")
    base_raw = Path("raw-data/millitome")
    base_output = Path("output-data/millitome")

    if not base_input.exists():
        raise FileNotFoundError(f"Input base path not found: {base_input}")

    for millitome in base_input.iterdir():
        if millitome.is_dir():
            for version_folder in millitome.iterdir():
                if version_folder.is_dir():
                    relative_path = version_folder.relative_to(base_input)
                    cur_millitome = str(relative_path)
                    config_file = version_folder / "config.yaml"
                    raw_data_path = base_raw / relative_path
                    output_path = base_output / relative_path
                    stage1_projection_path = raw_data_path / "projections.pickle.gz"

                    if not config_file.exists():
                        log.warning(
                            f"[{cur_millitome}] Skipping: config.yaml not found"
                        )
                        continue

                    log.info(f"\n--- Running pipeline for: {cur_millitome} ---")

                    stage1_cmd = [
                        "python",
                        "-m",
                        "hra_amap.cli.registration_stage_1",
                        "--config",
                        str(config_file),
                        "--output_path",
                        str(raw_data_path),
                    ]
                    run_command(stage1_cmd, cur_millitome)

                    stage2_cmd = [
                        "python",
                        "-m",
                        "hra_amap.cli.registration_stage_2",
                        "--stage1_projection_path",
                        str(stage1_projection_path),
                        "--output_path",
                        str(output_path),
                        "--config",
                        str(config_file),
                    ]
                    run_command(stage2_cmd, cur_millitome)


if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        log.error("Pipeline failed!")
        raise e
