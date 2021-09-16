from gadfly.utils import file_sha256, cwd
from gadfly.cli import colors, pp_exc, pp_err_details
import subprocess


def sh(cmd: str, echo=True, shell=True, check=False, desc=None, **kwargs) -> subprocess.CompletedProcess:
    if desc:
        print(f"{colors.R_CYAN}{desc}{colors.RESET}")
    if echo:
        print(f"{colors.RB_GREEN}> {colors.R_BLUE}{cmd}{colors.RESET}")

    kwargs["shell"] = shell
    kwargs["check"] = check
    return subprocess.run(cmd, **kwargs)
