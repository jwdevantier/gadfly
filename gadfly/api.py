from gadfly.utils import file_sha256, cwd
from gadfly.cli import colors, pp_exc, pp_err_details
import subprocess


def sh(cmd: str, echo=True, shell=True, check=False, desc=None, **kwargs) -> subprocess.CompletedProcess:
    if desc:
        print(f"{colors.CYAN}{desc}{colors.CLR}")
    if echo:
        print(f"{colors.B_GREEN}> {colors.BLUE}{cmd}{colors.CLR}")

    kwargs["shell"] = shell
    kwargs["check"] = check
    return subprocess.run(cmd, **kwargs)
