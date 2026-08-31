from pathlib import Path

def get_root_path() -> Path:
    "Returns the absolute path to the repo root"
    # this is a relatively simple logic to get to the path of the root of the repo
    # the breaking case i'd imagine is when the repository is cloned within nested hra-amap/* dirs (highly unlikely)
    CURR_DIR = Path.cwd()
    BASE_DIR = [directory for directory in [CURR_DIR] + list(CURR_DIR.parents) if not str(directory).split('hra-amap')[-1]].pop()
    return BASE_DIR

def get_bcpd_path() -> Path:
    """
    Returns the absolute path to the BCPD directory.
    Raises an exception if not found with a link to install instructions.
    """
    # builds the bcpd directory path much more cleanly from the repo root (see get_root_path)
    # assumes that the bcpd repo will be cloned at the same level as that of the root (this is made explicit in the instructions, see BCPD_INSTALLATION.md and README.md)
    BASE_DIR = get_root_path()
    BCPD_DIR = BASE_DIR.joinpath('bcpd')
    BCPD_EXEC = BCPD_DIR.joinpath('bcpd')
    if not BCPD_EXEC.is_file():
        raise FileNotFoundError("BCPD executable not found. BCPD Install instructions:  https://github.com/cns-iu/hra-amap/blob/main/BCPD_INSTALLATION.md")

    return BCPD_DIR
