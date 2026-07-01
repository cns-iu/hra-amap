import os
from pathlib import Path

def get_root_path() -> Path:
    "Returns the absolute path to the repo root"
    # this is a relatively simple logic to get to the path of the root of the repo
    # the breaking case i'd imagine is when the repository is cloned within nested hra-amap/* dirs (highly unlikely)
    BASE_DIR = [parent for parent in Path.cwd().parents if not str(parent).split('hra-amap')[-1]].pop()
    return BASE_DIR

def get_bcpd_executable_path() -> tuple[Path, Path]:
    """
    Returns the absolute path to the BCPD executable.
    Raises an exception if not found with a link to install instructions.
    """
    # builds the bcpd directory and executable paths much more cleanly from the repo root (see get_root_path)
    # assumes that the bcpd repo will be cloned at the same level as that of the root (this is made explicit in the instructions, see BCPD_INSTALLATION.md and README.md)
    BASE_DIR = get_root_path()
    if not BASE_DIR:
        raise FileNotFoundError("BCPD directory not found. BCPD Install instructions:  https://github.com/cns-iu/hra-amap/blob/main/BCPD_INSTALLATION.md")
    BCPD_DIR = BASE_DIR.joinpath('bcpd')
    bcpd_executable = BCPD_DIR.joinpath('bcpd')
    return (BCPD_DIR, bcpd_executable)