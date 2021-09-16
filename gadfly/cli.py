from typing import Optional
import sys
import traceback


class colors:
    """ANSI color escape codes"""

    RESET = "\033[0m"
    BOLD = "\033[1m"

    GREY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    R_GREY = "\033[0m\033[90m"
    R_RED = "\033[0m\033[91m"
    R_GREEN = "\033[0m\033[92m"
    R_YELLOW = "\033[0m\033[93m"
    R_BLUE = "\033[0m\033[94m"
    R_MAGENTA = "\033[0m\033[95m"
    R_CYAN = "\033[0m\033[96m"
    R_WHITE = "\033[0m\033[97m"

    RB_GREY = "\033[0m\033[1m\033[90m"
    RB_RED = "\033[0m\033[1m\033[91m"
    RB_GREEN = "\033[0m\033[1m\033[92m"
    RB_YELLOW = "\033[0m\033[1m\033[93m"
    RB_BLUE = "\033[0m\033[1m\033[94m"
    RB_MAGENTA = "\033[0m\033[1m\033[95m"
    RB_CYAN = "\033[0m\033[1m\033[96m"
    RB_WHITE = "\033[0m\033[1m\033[97m"


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


def pp_exc():
    typ, val, tb = sys.exc_info()
    if typ is None and val is None and tb is None:
        raise RuntimeError("must be called from within an exception")
    exc_name = typ.__name__
    print(f"{colors.RESET}{colors.BOLD}{colors.RED}--- {exc_name} Trace Begin ---{colors.RESET}")
    traceback.print_exception(typ, val, tb)
    print(f"{colors.RESET}{colors.BOLD}{colors.RED}--- {exc_name} Trace End ---{colors.RESET}")


def pp_err_details(msg: str, details: dict):
    print(f"{colors.RB_RED}>{colors.RB_WHITE} {msg}")
    for label, val in details.items():
        print(f"  * {colors.RB_YELLOW}{str(label)}: {colors.RB_WHITE}{str(val)}")
    print(f"{colors.RESET}", end="", flush=True)


def info(msg: str):
    print(f"{colors.RB_MAGENTA}> {colors.RB_WHITE}{msg}{colors.RESET}")