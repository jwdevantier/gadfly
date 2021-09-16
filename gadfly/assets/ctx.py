from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from gadfly.config import Config


@dataclass(frozen=True)
class AssetCtx:
    # overall config, always provided
    config: Config
    # dir to assets, always provided
    asset_dir: Path
    # whether compiling in dev-mode (watch server) or for production
    dev_mode: bool
    # file asset -- only provided in watch mode where something happened
    file: Optional[Path] = None
