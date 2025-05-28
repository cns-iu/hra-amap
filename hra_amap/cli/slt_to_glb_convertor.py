import trimesh
import argparse
from pathlib import Path
import re
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Convert folder of .stl files to single .glb"
    )
    parser.add_argument(
        "--stl_dir", required=True, help="Directory containing .stl files"
    )
    parser.add_argument(
        "--glb",
        required=True,
        help="Path to output .glb file (.glb extension required)",
    )
    args = parser.parse_args()

    stl_dir = Path(args.stl_dir)
    output_path = Path(args.glb)

    if not stl_dir.exists() or not stl_dir.is_dir():
        sys.exit(
            f"Error: Provided --stl_dir '{stl_dir}' does not exist or is not a directory."
        )

    if output_path.suffix.lower() != ".glb":
        sys.exit("Error: Output file must have a .glb extension.")

    scene = trimesh.Scene()
    for stl_file in sorted(stl_dir.glob("*.stl")):
        try:
            mesh = trimesh.load(stl_file, file_type="stl")
            name = stl_file.stem
            match = re.search(r"(\d+)$", name)
            number = match.group(1)
            scene.add_geometry(mesh, geom_name=number, node_name=number)

        except Exception as e:
            print(f"Error loading '{stl_file.name}': {e}")

    scene.export(file_obj=output_path)
    print(f"Exported combined GLB to: {output_path}")


if __name__ == "__main__":
    main()
