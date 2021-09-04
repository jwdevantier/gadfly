from gadfly.config import Config
import multiprocessing as mp
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path


def context_main_file(config: Config) -> Path:
    return config.project_root / "context" / "__main__.py"


def update_context_inner(queue: mp.Queue, config: Config):
    fpath = context_main_file(config)
    spec = spec_from_file_location("module.name", fpath)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    queue.put(mod.main(config))


def update_context(config: Config):
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    # TODO: check that file exists using context_main_file(config)
    p = ctx.Process(target=update_context_inner, args=(queue, config))
    p.start()
    result = queue.get()
    config.context = result
