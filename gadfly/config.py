from pathlib import Path
from typing import Union

DEFAULT_CONFIG = """\
[project]
# where to find your posts/pages
pages = "pages"
# where to find jinja2 templates
templates = "templates"
# where the python code responsible for providing the context
# on-asset-changed handlers and more will be located.
code = "blogcode"
# where the generated website content goes
output = "output"

# Example asset handler
# [assets.css]
# handler = "on_css"

# Example asset handler
# [assets.css]
# command = "npx postcss-cli {file} --dir {output}/css/{file.name}"
"""


class AssetHandler:
    def __init__(self, opts: dict):
        if "handler" in opts:
            self.handler = opts["handler"]
        elif "command" in opts:
            self.handler = ""

    def handle(self, file):
        pass


class Config:

    def __init__(self,
                 project_root: Path,
                 silent: bool = False,
                 pages: str = "pages",
                 output: str = "output",
                 templates: str = "templates",
                 code: str = "code",
                 assets: dict = None):
        self.__project_root = project_root.absolute()
        self.assets = assets
        self.pages_path = pages
        self.output_path = output
        self.templates_path = templates
        self.user_code_path = code

        self.silent = silent
        self.context = {}
        self.page_md = {}

    @property
    def project_root(self) -> Path:
        return self.__project_root

    def __path_coerce(self, label: str, val: Union[str, Path]) -> Path:
        if isinstance(val, str):
            val = Path(val)
        new_val = (self.project_root / val).resolve()
        if new_val == self.project_root:
            raise ValueError(f"invalid {label} dir, path '{val}' resolves to the project directory")
        if not new_val.exists():
            raise ValueError(f"invalid {label} dir, '{new_val}' does not exist!")
        elif not new_val.is_dir():
            raise ValueError(f"invalid {label} dir, '{new_val}' is not a directory!")
        return new_val

    @property
    def pages_path(self) -> Path:
        return self.__pages_path

    @pages_path.setter
    def pages_path(self, val: Union[str, Path]):
        self.__pages_path = self.__path_coerce("pages", val)

    @property
    def output_path(self) -> Path:
        return self.__output_path

    @output_path.setter
    def output_path(self, val: Union[str, Path]):
        self.__output_path = self.__path_coerce("output", val)

    @property
    def templates_path(self) -> Path:
        return self.__templates_path

    @templates_path.setter
    def templates_path(self, val: Union[str, Path]):
        self.__templates_path = self.__path_coerce("templates", val)

    @property
    def user_code_path(self) -> Path:
        return self.__user_code_path

    @user_code_path.setter
    def user_code_path(self, val: Union[str, Path]):
        self.__user_code_path = self.__path_coerce("code", val)

    @property
    def user_code_file(self) -> Path:
        return self.user_code_path / "__init__.py"

    def __repr__(self):
        attr_vals = [
            f"{attr}: {getattr(self, attr)}"
            for attr in ["project_root", "silent", "pages_path", "output_path", "templates_path", "user_code_path"]
        ]
        return f"""<{type(self).__name__}, {", ".join(attr_vals)}>"""

    def __str__(self):
        return self.__repr__()


class AssetValidationError(Exception):
    def __init__(self, asset_name: str, asset_path: Path, message: str):
        self.asset_name = asset_name
        self.asset_path = asset_path
        super().__init__(f"error in asset '{asset_name}' entry: {message}")


class AssetHandlerAndCommandError(AssetValidationError):
    def __init__(self, asset_name: str, asset_path: Path):
        super().__init__(
            asset_name, asset_path,
            f"asset entry has both a 'command' and a 'handler' entry - choose one")


class AssetCommandKeyError(AssetValidationError):
    def __init__(self, asset_name: str, asset_path: Path, key: str):
        self.key = key
        super().__init__(
            asset_name, asset_path,
            f"command uses key '{key}' which is not a provided during evaluation"
        )


class AssetPathNotExists(AssetValidationError):
    def __init__(self, asset_name: str, asset_path: Path):
        super().__init__(asset_name, asset_path, f"path '{asset_path}' does not exist")


class AssetPathNotADir(AssetValidationError):
    def __init__(self, asset_name: str, asset_path: Path):
        super().__init__(asset_name, asset_path, f"path '{asset_path}' does not a directory")


def read_config(project_path: Path, conf_dict: dict) -> Config:
    project_root: Path = project_path.absolute()
    # TODO: check project_root, must exist and be a directory
    assets = conf_dict.get("assets", {})
    for asset_name, opts in assets.items():
        asset_path = project_root / opts.get("dir", asset_name)
        if not asset_path.exists():
            raise AssetPathNotExists(asset_name, asset_path)
        elif not asset_path.is_dir():
            raise AssetPathNotADir(asset_name, asset_path)
        if "command" in opts and "handler" in opts:
            raise AssetHandlerAndCommandError(asset_name, asset_path)
        if "handler" in opts:
            # could try to resolve string to a module attr, but this can change
            # later on anyway as code is changed while the watch-loop runs.
            pass
        elif "command" in opts:
            # ensure we aren't using any vars not provided
            try:
                # TODO: provide keys which we intend to evaluate a command string
                #       with here.
                opts["command"].format(file=Path(""), output=Path(""))
            except KeyError as e:
                raise AssetCommandKeyError(asset_name, asset_path, str(e).strip("'")) from KeyError
            pass
        # write asset path back to asset's opts. will use this later when starting
        # asset listeners.
        opts["dir"] = asset_path

    return Config(
        project_root=project_root,
        **{k: v for k,v in conf_dict.get("project", {}).items()
           if k in {"pages", "templates", "code", "output"}},
        **{"assets": assets}
    )


config: Config
