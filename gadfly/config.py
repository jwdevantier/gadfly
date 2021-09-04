from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    project_root: Path
    silent: bool
    context: field(default_factory=dict)
    page_md: field(default_factory=dict)

    @property
    def pages_path(self) -> Path:
        return (self.project_root / "pages").resolve()

    @property
    def output_path(self) -> Path:
        return (self.project_root / "output").resolve()

    @property
    def templates_path(self) -> Path:
        return (self.project_root / "templates").resolve()

    @property
    def context_files_path(self) -> Path:
        return (self.project_root / "context").resolve()


config: Config
