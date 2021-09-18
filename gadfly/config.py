from pathlib import Path
from typing import Union
from gadfly.assets.errors import *
from importlib.util import find_spec
from typing import Optional


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


class ConfigCodeSection:
    def __init__(self, *,
                 module: str = "blogcode",
                 context_hook: str = "context",
                 post_compile_hook: str = "post_compile"):
        self.__module = module
        mod = find_spec(module)
        if mod is None:
            raise ValueError(f"could not find module {module}")
        self.__module_path = mod.origin
        self.__context_hook = context_hook
        self.__post_compile_hook = post_compile_hook

    @property
    def module(self) -> str:
        return self.__module

    @property
    def module_path(self) -> str:
        return self.__module_path

    @property
    def context_hook(self) -> str:
        return self.__context_hook

    @property
    def post_compile_hook(self) -> str:
        return self.__post_compile_hook

    def __repr__(self):
        attrs = ", ".join(f"""{attr}: {getattr(self, attr)}""" for attr in [
            "module", "context_hook", "post_compile_hook"
        ])
        return f"<{type(self).__name__} {attrs}>"

    def __str__(self):
        return self.__repr__()


class Config:
    def __init__(self,
                 project_root: Path,
                 silent: bool = False,
                 pages: str = "pages",
                 output: str = "output",
                 templates: str = "templates",
                 code: Optional[ConfigCodeSection] = None,
                 assets: dict = None,
                 dev_mode: bool = True):
        self.__project_root = project_root.absolute()
        self.silent = silent
        self.pages_path = pages
        self.output_path = output
        self.templates_path = templates
        self.code = code if code is not None else ConfigCodeSection()
        self.assets = assets
        self.dev_mode = dev_mode

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

    def __repr__(self):
        attr_vals = [
            f"{attr}: {getattr(self, attr)}"
            for attr in ["project_root", "silent", "pages_path", "output_path", "templates_path", "code"]
        ]
        return f"""<{type(self).__name__}, {", ".join(attr_vals)}>"""

    def __str__(self):
        return self.__repr__()


def read_config(project_path: Path, conf_dict: dict) -> Config:
    project_root: Path = project_path.absolute()
    # TODO: check project_root, must exist and be a directory
    conf_assets = conf_dict.get("assets", {})
    for asset_name, opts in conf_assets.items():
        asset_path = project_root / opts.get("dir", asset_name)
        # write asset path back to asset's opts. will use this later when starting
        # asset listeners.
        opts["dir"] = asset_path
        if not asset_path.exists():
            raise AssetPathNotExistsError(asset_name, asset_path)
        elif not asset_path.is_dir():
            raise AssetPathNotADirError(asset_name, asset_path)
        elif "handler" not in opts:
            raise AssetHandlerMissingError(asset_name, asset_path)

    code_section = ConfigCodeSection(**conf_dict.get("code", {}))
    return Config(
        project_root=project_root,
        **{k: v for k, v in conf_dict.get("project", {}).items()
           if k in {"pages", "templates", "output"}},
        **{"assets": conf_assets, "code": code_section}
    )


config: Config
