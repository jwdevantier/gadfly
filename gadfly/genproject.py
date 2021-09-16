from pathlib import Path
from gadfly.config import DEFAULT_CONFIG


def genproject(project_root: Path):
    pass


def genconf(conf_path: Path):
    """write default config to file at `conf_path`."""
    with open(conf_path, "w") as fh:
        fh.write(DEFAULT_CONFIG)
