from dataclasses import dataclass
from pathlib import Path
from typing import Optional
# from gadfly.config import Config
#
#
# @dataclass
# class AssetCtx:
#     # overall config, always provided
#     config: Config
#     # dir to assets, always provided
#     asset_dir: Path
#     # file asset -- only provided in watch mode where something happened
#     file: Optional[Path]
#     # whether compiling in dev-mode (watch server) or for production
#     dev_mode: bool


class AssetValidationError(Exception):
    def __init__(self, asset_name: str, asset_path: Path, message: str):
        self.asset_name = asset_name
        self.asset_path = asset_path
        super().__init__(f"error in asset '{asset_name}' entry: {message}")


class AssetPathNotExistsError(AssetValidationError):
    def __init__(self, asset_name: str, asset_path: Path):
        super().__init__(asset_name, asset_path, f"path '{asset_path}' does not exist")


class AssetPathNotADirError(AssetValidationError):
    def __init__(self, asset_name: str, asset_path: Path):
        super().__init__(asset_name, asset_path, f"path '{asset_path}' does not a directory")


class AssetHandlerMissingError(AssetValidationError):
    def __init__(self, asset_name: str, asset_path: Path):
        super().__init__(
            asset_name,
            asset_path,
            # TODO: revisit - fix up example path to fn here, take Config obj if need be
            f"no handler entry - must point to a handler function to trigger, e.g. 'blogcode.handlers:on_{asset_name}'")


class AssetHandlerError(AssetValidationError):
    def __init__(self,
                 asset_name: str,
                 asset_dir: Path,
                 handler: str,
                 fn: str,
                 module: str,
                 module_fpath: str,
                 message: str):
        super().__init__(
            asset_name, asset_dir,
            f"handler '{handler}': {message}"
        )
        self.handler = handler
        self.handler_fn = fn
        self.handler_module = module
        self.handler_module_fpath = module_fpath


class AssetHandlerNotFoundError(AssetHandlerError):
    def __init__(self,
                 asset_name: str,
                 asset_dir: Path,
                 handler: str,
                 fn: str,
                 module: str,
                 module_fpath: str):
        super().__init__(
            asset_name, asset_dir,
            handler, fn, module, module_fpath,
            f"fn {fn} not found in module file {module_fpath}"
        )


class AssetHandlerNotCallableError(AssetHandlerError):
    def __init__(self,
                 asset_name: str,
                 asset_dir: Path,
                 handler: str,
                 fn: str,
                 module: str,
                 module_fpath: str):
        super().__init__(
            asset_name, asset_dir,
            handler, fn, module, module_fpath,
            f"fn {fn} in module {module} (file {module_fpath}) not a callable!"
        )

