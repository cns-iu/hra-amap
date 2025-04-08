from pathlib import Path

INPUT_DATA_DIR = "input-data"
SOURCE_DIR = "source"

def extract_relative_path(source_path: str) -> Path:
    """
    Extracts the relative path between 'input-data/' and 'source/'.
    
    :param source_path: The full path to a file inside input-data/
    :return: Path object representing the extracted relative path
    """
    path_parts = Path(source_path).parts

    if INPUT_DATA_DIR not in path_parts or SOURCE_DIR not in path_parts:
        raise ValueError(f"Path must contain '{INPUT_DATA_DIR}' and '{SOURCE_DIR}': {source_path}")

    input_index = path_parts.index(INPUT_DATA_DIR)
    source_index = path_parts.index(SOURCE_DIR)

    if source_index <= input_index + 1:
        raise ValueError(f"Invalid path structure: '{SOURCE_DIR}' should be deeper inside '{INPUT_DATA_DIR}': {source_path}")

    return Path(*path_parts[input_index + 1:source_index])


def create_directory(base_dir: str, relative_path: Path) -> Path:
    """
    Creates a directory inside the specified base directory using the given relative path.
    
    :param base_dir: The base directory where the relative path should be created
    :param relative_path: The relative path extracted from the source
    :return: Path object representing the newly created directory
    """
    new_dir = Path(base_dir) / relative_path

    try:
        new_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise

    return new_dir
