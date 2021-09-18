from typing import Optional
import sys
import traceback


class colors:
    """ANSI color escape codes"""

    CLR = "\033[0m"
    BOLD = "\033[1m"

    GREY = "\033[0m\033[90m"
    RED = "\033[0m\033[91m"
    GREEN = "\033[0m\033[92m"
    YELLOW = "\033[0m\033[93m"
    BLUE = "\033[0m\033[94m"
    MAGENTA = "\033[0m\033[95m"
    CYAN = "\033[0m\033[96m"
    WHITE = "\033[0m\033[97m"

    B_GREY = "\033[0m\033[1m\033[90m"
    B_RED = "\033[0m\033[1m\033[91m"
    B_GREEN = "\033[0m\033[1m\033[92m"
    B_YELLOW = "\033[0m\033[1m\033[93m"
    B_BLUE = "\033[0m\033[1m\033[94m"
    B_MAGENTA = "\033[0m\033[1m\033[95m"
    B_CYAN = "\033[0m\033[1m\033[96m"
    B_WHITE = "\033[0m\033[1m\033[97m"


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
    print(f"{colors.CLR}{colors.BOLD}{colors.RED}--- {exc_name} Trace Begin ---{colors.CLR}")
    traceback.print_exception(typ, val, tb)
    print(f"{colors.CLR}{colors.BOLD}{colors.RED}--- {exc_name} Trace End ---{colors.CLR}")


def pp_err_details(msg: str, details: dict):
    print(f"{colors.B_RED}>{colors.B_WHITE} {msg}")
    for label, val in details.items():
        print(f"  * {colors.B_YELLOW}{str(label)}: {colors.B_WHITE}{str(val)}")
    print(f"{colors.CLR}", end="", flush=True)


def info(msg: str):
    print(f"{colors.B_MAGENTA}> {colors.B_WHITE}{msg}{colors.CLR}")