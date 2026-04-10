import argparse
import sys
from pathlib import Path
import trimesh
from typing import List, Tuple, Set

PREFIXES = ("VHM-", "VHF-")

def clean_label(node_name: str) -> str:
    """
    Normalize node labels by removing known prefixes (e.g., VHM-, VHF-).
    Parameters:
        node_name : str -> Original node name from scene graph.
    Returns:
        str: Cleaned label or empty string if invalid.
    """
    if not node_name or not isinstance(node_name, str):
        return ""

    for prefix in PREFIXES:
        if node_name.startswith(prefix):
            return node_name[len(prefix):]

    return node_name

def is_valid_mesh(mesh: trimesh.Trimesh) -> bool:
    """
        Validate mesh to ensure it is usable for downstream operations.
        Filters out:
            - Empty meshes
            - Non-Trimesh objects
            - Zero-area meshes (prevents OBB crash)
        Returns
            bool
                True if mesh is valid, False otherwise.
    """
    if mesh is None:
        return False

    if not isinstance(mesh, trimesh.Trimesh):
        return False

    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        return False

    if mesh.area == 0:
        return False

    return True

def process_scene(scene: trimesh.Scene) -> List[Tuple[str, trimesh.Trimesh]]:
    """
    Extract meshes using NODE GRAPH.
    Returns list of (label, mesh)
    """
    processed = []
    seen = set()

    for node_name in scene.graph.nodes_geometry:
        try:
            geom_entry = scene.graph.get(node_name)
            if geom_entry is None:
                continue

            geom_name = geom_entry[1]

            # Validate geometry mapping
            if geom_name is None or geom_name not in scene.geometry:
                continue

            label = clean_label(node_name)

            # Skip duplicates / invalid
            if not label or label in seen:
                continue
            seen.add(label)

            geom = scene.geometry[geom_name]

            if not is_valid_mesh(geom):
                print(f"[WARN] Skipping invalid mesh: {node_name}")
                continue

            if not isinstance(geom, trimesh.Trimesh):
                continue

            processed.append((label, geom))

        except Exception as e:
            print(f"[WARN] Failed node '{node_name}': {e}")
            continue

    return processed

def load_and_process(glb_file: Path) -> List[Tuple[str, trimesh.Trimesh]]:
    """
    Load GLB and extract processed meshes using node graph.
    """
    try:
        loaded = trimesh.load(glb_file, force="scene")

        if isinstance(loaded, trimesh.Scene):
            return process_scene(loaded)

        elif isinstance(loaded, trimesh.Trimesh):
            # fallback (no graph available)
            return [(clean_label(glb_file.stem), loaded)]

        else:
            print(f"[WARN] Unsupported type in {glb_file.name}")
            return []

    except Exception as e:
        print(f"[ERROR] Failed loading '{glb_file.name}': {e}")
        return []


def merge_scenes(glb_dir: Path) -> trimesh.Scene:
    """
    Merge all GLB files using NODE LABELS (correct pipeline logic)
    """
    scene = trimesh.Scene()
    seen: Set[str] = set()

    for glb_file in sorted(glb_dir.glob("*.glb")):
        items = load_and_process(glb_file)

        for label, geom in items:
            if label in seen:
                continue
            seen.add(label)

            scene.add_geometry(
                geom,
                geom_name=label,
                node_name=label
            )

    return scene


def validate_paths(glb_dir: Path, output_path: Path):
    if not glb_dir.exists() or not glb_dir.is_dir():
        sys.exit(f"Error: --glb_dir '{glb_dir}' is not a valid directory.")

    if output_path.suffix.lower() != ".glb":
        sys.exit("Error: Output file must have a .glb extension.")

    output_path.parent.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Merge GLB files using node-based labels"
    )
    parser.add_argument("--glb_dir", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    glb_dir = Path(args.glb_dir)
    output_path = Path(args.output)

    validate_paths(glb_dir, output_path)

    print(f"[INFO] Processing GLBs from: {glb_dir}")

    scene = merge_scenes(glb_dir)

    if not scene.geometry:
        sys.exit("Error: No valid geometry found to export.")

    scene.export(file_obj=output_path)

    print(f"[SUCCESS] Exported merged GLB to: {output_path}")


if __name__ == "__main__":
    main()