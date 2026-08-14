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


def run_command(cmd, cur_millitome, stream=False):
    """
    Execute a shell command
    """
    log.info(f"[{cur_millitome}] Running: {' '.join(str(x) for x in cmd)}")
    result = subprocess.run(cmd) if stream else subprocess.run(
        cmd, capture_output=True, text=True
    )
    if result.returncode != 0:
        stdout = "" if stream else result.stdout
        stderr = "" if stream else result.stderr
        raise RuntimeError(
            f"[{cur_millitome}] Command failed!\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
    if not stream:
        log.info(result.stdout)


def run_pipeline(args):
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
                        "--point_cloud_output_path",
                        str(output_path),
                    ]
                    if args.volumetric:
                        stage1_cmd.append("--volumetric")
                    if not args.progress:
                        stage1_cmd.append("--quiet")
                    run_command(stage1_cmd, cur_millitome, stream=args.progress)

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
                    run_command(stage2_cmd, cur_millitome, stream=args.progress)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run all Millitome registrations")
    parser.add_argument(
        "--volumetric",
        action="store_true",
        help="Use original surface vertices plus Open3D visual-hull volume controls.",
    )
    parser.add_argument(
        "--quiet",
        action="store_false",
        dest="progress",
        default=True,
        help="Disable registration progress bars.",
    )
    args = parser.parse_args()

    try:
        run_pipeline(args)
    except Exception as e:
        log.error("Pipeline failed!")
        raise e


if __name__ == "__main__":
    main()
