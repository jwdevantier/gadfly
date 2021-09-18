from gadfly.config import Config
from typing import Union
from pathlib import Path
from hashlib import sha256
from watchdog.events import FileSystemEvent
from contextlib import contextmanager
import os


def file_sha256(fpath: Union[str, Path]) -> str:
    with open(fpath, "rb") as fh:
        return sha256(fh.read()).hexdigest()


def is_page(event: FileSystemEvent) -> bool:
    return ((not event.is_directory)
            and event.src_path.endswith(".md"))


def delete_output(path: Path):
    path.unlink(missing_ok=True)
    if path.name == "index.html":
        # will error out if dir is not empty, that's OK.
        # TODO: test, capture error and print relevant message
        path.parent.rmdir()


def page_path(config: Config, output_path: Path) -> Path:
    if not output_path.suffix == ".html":
        raise RuntimeError("expected html file")
    fpath = output_path.relative_to(config.output_path)
    if fpath.name == "index.html":
        fpath = Path(*fpath.parts[:-2]) / (fpath.parts[-2] + ".md")
    else:
        fpath = fpath.parent / (fpath.name[:-len(fpath.suffix)] + ".md")
    fpath = config.pages_path / fpath
    return fpath


def output_path(config: Config, page_path: Path) -> Path:
    if not page_path.suffix == ".md":
        raise RuntimeError("expected markdown file")
    fpath = page_path.relative_to(config.pages_path)
    return config.output_path / fpath.parent / (fpath.name[:-len(".md")]) / "index.html"


@contextmanager
def cwd(path: Union[str, Path]):
    """Change working directory for the duration of the context manager"""

    curr_cwd = Path.cwd()
    if not isinstance(path, Path):
        if not isinstance(path, str):
            raise TypeError(f"expected path or string, got {type(path).__name__}")
        path = Path(path)
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(curr_cwd)


__all__ = [
    "file_sha256",
    "is_page",
    "delete_output",
    "page_path",
    "output_path",
    "cwd",
]
