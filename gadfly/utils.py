from gadfly import config


def info(msg: str):
    if not config.config.silent:
        print(msg)
