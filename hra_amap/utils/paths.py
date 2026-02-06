import os
from pathlib import Path


def get_bcpd_executable_path():
    """
    Returns the absolute path to the BCPD executable.
    Raises an exception if not found with a link to install instructions.
    """
    BASE_DIR = Path.cwd()
    BCPD_DIR = Path(os.getenv("BCPD_DIR", ""))
    bcpd_executable = [
        BCPD_DIR / "bcpd",
        BASE_DIR / "bcpd" / "bcpd",
        BASE_DIR.parent / "bcpd" / "bcpd",
        BASE_DIR.parent.parent / "bcpd" / "bcpd",
        BASE_DIR.parent.parent.parent / "bcpd" / "bcpd",
    ]
    for path in bcpd_executable:
        if path.is_file():
            return path.parent.resolve(), path.resolve()

    raise FileNotFoundError(
        "BCPD executable not found in expected locations:\n"
        f"  1. {bcpd_executable[0]}\n"
        f"  2. {bcpd_executable[1]}\n"
        f"  3. {bcpd_executable[2]}\n\n"
        f"  4. {bcpd_executable[3]}\n\n"
        f"  5. {bcpd_executable[4]}\n\n"
        "BCPD Install instructions:  https://github.com/cns-iu/hra-amap/blob/main/BCPD_INSTALLATION.md"
    )
