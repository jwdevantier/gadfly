
from gadfly.config import Config
from gadfly import config
from typing import Union, Optional
from pathlib import Path
from hashlib import sha256
from watchdog.events import FileSystemEvent


def info(msg: str):
    if not config.config.silent:
        print(msg)


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


def prompt_yes_no(question: str, default: Optional[bool] = True) -> bool:
    """Pose a question, accepting y|yes / n|no as answer"""
    if not (isinstance(default, bool) or default is None):
        raise TypeError("'default' must be None|True|False")
    prompt = {True: "[Y/n]", False: "[y/N]", None: "[y/n]"}[default]
    choices = {"y": True, "yes": True, "n": False, "no": False}
    while True:
        print(f"{question} {prompt}: ", end="", flush=True)
        choice = input().lower()
        if choice == "" and default is not None:
            return default
        elif choice in choices:
            return choices[choice]
        else:
            print(f"  invalid input '{choice}', please respond with y/yes/n/no", flush=True)


__all__ = [
    "file_sha256",
    "is_page",
    "delete_output",
    "page_path",
    "output_path",
    "prompt_yes_no",
]
