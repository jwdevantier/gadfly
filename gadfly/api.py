from gadfly.utils import file_sha256, cwd
from gadfly.cli import colors, pp_exc, pp_err_details
from gadfly import Config
from gadfly.page_hooks_api import PagePreCompileHookFn, PagePostCompileHookFn
from typing import Dict, Any
import subprocess


class RenderPageFn:
    def __call__(self, page: str, template: str, context: Dict[str, Any]) -> None:
        ...


def sh(cmd: str, echo=True, shell=True, check=False, desc=None, **kwargs) -> subprocess.CompletedProcess:
    if desc:
        print(f"{colors.B_MAGENTA}> {colors.B_GREY}{desc}{colors.CLR}")
    if echo:
        print(f"{colors.B_BLUE}> {colors.B_GREY}{cmd}{colors.CLR}")

    kwargs["shell"] = shell
    kwargs["check"] = check
    return subprocess.run(cmd, **kwargs)
