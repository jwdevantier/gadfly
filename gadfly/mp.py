import multiprocessing as mp
from multiprocessing.connection import wait as mp_wait
from multiprocessing.process import BaseProcess
from multiprocessing.context import BaseContext
import importlib
from typing import Callable, Tuple, Dict, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileSystemMovedEvent
from gadfly.utils import *
from gadfly import config
from gadfly import compiler
from gadfly.assets.errors import *
from gadfly.assets.ctx import AssetCtx
from gadfly import cli
from gadfly.cli import colors
from queue import Empty as QueueEmpty
from dataclasses import dataclass
import time


class EventType:
    CONTEXT_CHANGED = "context_changed"
    PAGE_CHANGED = "page_changed"
    TEMPLATE_CHANGED = "template_changed"
    ASSET_CHANGED = "asset_changed"
    STOP = "stop"


class StopQueueType:
    EXCEPTION = "exception"


class ConsumerProcessFatalError(Exception):
    pass


@dataclass
class ConsumerProcess:
    input_queue: mp.Queue
    target: Callable
    args: Tuple
    process: Optional[BaseProcess] = None

    def spawn(self, *, ctx: Optional[BaseContext] = None) -> BaseProcess:
        if ctx:
            p = ctx.Process(target=self.target, args=(self.input_queue, *self.args))
        else:
            p = mp.Process(target=self.target, args=(self.input_queue, *self.args))
        self.process = p
        return p

    def stop(self):
        self.input_queue.put({"type": EventType.STOP})


class BaseEventHandler(FileSystemEventHandler):
    def __init__(self, queue: mp.Queue):
        self._db = {}
        self._queue = queue

    def hash_db_clear(self, fpath: str):
        del self._db[fpath]

    def hash_db_set(self, fpath: str):
        """Forcefully set entry's hash.
        NOTE: do not use if already calling `is_file_changed`."""
        self._db[fpath] = file_sha256(fpath)

    def hash_db_update(self, fpath) -> bool:
        old_hash = self._db.get(fpath)
        new_hash = file_sha256(fpath)
        if old_hash != new_hash:
            self._db[fpath] = new_hash
            return True
        return False

    def send_event(self, event_type: str, payload: dict) -> None:
        self._queue.put({"type": event_type, "payload": payload})


class PageHandler(BaseEventHandler):
    def on_deleted(self, event: FileSystemEvent):
        """Delete corresponding compiled page"""
        if not is_page(event):
            return
        outpath = output_path(config.config, Path(event.src_path))
        delete_output(outpath)
        self.hash_db_clear(event.src_path)

    def on_moved(self, event: FileSystemMovedEvent):
        """Trigger delete"""
        if not is_page(event):
            return
        delete_output(output_path(
            config.config,
            Path(event.src_path)
        ))
        self.hash_db_clear(event.src_path)
        self.hash_db_update(event.dest_path)  # run for side-effects - updates hash entry
        self.send_event(EventType.PAGE_CHANGED, {"page": event.dest_path})

    def on_modified(self, event: FileSystemEvent):
        if not is_page(event):
            return
        if self.hash_db_update(event.src_path):
            self.send_event(EventType.PAGE_CHANGED, {"page": event.src_path})


class ContextCodeHandler(BaseEventHandler):
    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or not event.src_path.endswith(".py"):
            return
        if not self.hash_db_update(event.src_path):
            return
        self.send_event(EventType.CONTEXT_CHANGED, {})


class TemplateEventHandler(BaseEventHandler):
    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.send_event(EventType.TEMPLATE_CHANGED, {})


class AssetEventHandler(BaseEventHandler):
    def __init__(self, queue: mp.Queue, asset_name: str, asset_opts: dict):
        super().__init__(queue)
        self.asset_name = asset_name
        # no validation here, validation happens at the point of reading in
        # the configuration files.
        self.asset_opts = asset_opts

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if not self.hash_db_update(event.src_path):
            return
        self.send_event(EventType.ASSET_CHANGED, {
            "file": event.src_path,
            "asset_name": self.asset_name,
            "asset_opts": self.asset_opts,
        })


def get_code_hook(cfg: config.Config, hook_name: str) -> Optional[Callable]:
    mod = importlib.import_module(cfg.code.module)
    if not hasattr(mod, hook_name):
        return None
    hook = getattr(mod, hook_name)
    if not callable(hook):
        cli.pp_err_details(f"Invalid hook - {hook_name} is not a callable!",
                           {"module": cfg.code.module,
                            "module file": cfg.code.module_path,
                            "symbol": hook_name,
                            "symbol type": type(hook)})
        raise ConsumerProcessFatalError
    return hook


def _eval_context(cfg: config.Config) -> dict:
    # NOTE: _must_ be run within the context of a separate process.
    #       Otherwise, changes to modules would never take effect as the import
    #       system caches imports.

    # TODO: catch failure to load context file
    hook = get_code_hook(cfg, cfg.code.context_hook)
    if hook is None:
        cli.pp_err_details(
            f"invalid context -- expected a context hook function",
            {"module": cfg.code.module,
             "module file": cfg.code.module_path,
             "hook": cfg.code.context_hook})
        raise ConsumerProcessFatalError
    try:
        return hook(cfg)
    except Exception:
        cli.pp_exc()
        cli.pp_err_details(
            "Unhandled error while evaluating context hook, see stacktrace above for details",
            {"module": cfg.code.module,
             "module file": cfg.code.module_path,
             "hook": cfg.code.context_hook}
        )


def _compile_process_inner(queue: mp.Queue, stop_queue: mp.Queue, cfg: config.Config) -> None:
    # this globally assigned variable is not set in the new process.
    config.config = cfg
    # (re-)compute context, done once for duration of the compile-process' lifetime.
    cfg.context = _eval_context(cfg)
    post_compile_hook = get_code_hook(cfg, cfg.code.post_compile_hook) or (lambda x, y: None)

    # initialize templating engine instance
    j2env = compiler.get_j2env(cfg)

    def render_generated_page(page: str, template: str, context: dict) -> None:
        compiler.render_generated_page(Path(page), template, cfg, j2env, context)

    # render all pages using the newly computed context.
    compiler.render_all(cfg, j2env)
    post_compile_hook(cfg, render_generated_page)

    while True:
        event = queue.get(block=True)
        # Continue extracting events until queue empty OR STOP event received.
        # determine most far-reaching action based on event types.
        # If PAGE_CHAGED: recompile the page(s) affected
        # If TEMPLATE_CHANGED: recompile all pages
        # If CONTEXT_CHANGED: restart process (to recompute context), then recompile all pages
        action: str = EventType.PAGE_CHANGED
        pages = []
        try:
            while True:
                if event["type"] == EventType.PAGE_CHANGED:
                    pages.append(event["payload"]["page"])
                elif event["type"] == EventType.CONTEXT_CHANGED:
                    action = EventType.CONTEXT_CHANGED
                elif event["type"] == EventType.TEMPLATE_CHANGED and action == EventType.PAGE_CHANGED:
                    action = EventType.TEMPLATE_CHANGED
                elif event["type"] == EventType.STOP:
                    break
                # will immediately raise queue.Empty iff. queue is empty
                event = queue.get(block=False)
        except QueueEmpty:
            pass
        if action == EventType.PAGE_CHANGED:
            for page in pages:
                compiler.render(cfg, j2env, Path(page))
            post_compile_hook(cfg, render_generated_page)
        elif action == EventType.TEMPLATE_CHANGED:
            compiler.render_all(cfg, j2env)
            post_compile_hook(cfg, render_generated_page)
        elif action == EventType.CONTEXT_CHANGED:
            return
        else:
            raise RuntimeError("unknown action")

        if event["type"] == EventType.STOP:
            stop_queue.put(0)
            return


def _compile_process(queue: mp.Queue, stop_queue: mp.Queue, cfg: config.Config) -> None:
    try:
        _compile_process_inner(queue, stop_queue, cfg)
    except ConsumerProcessFatalError:
        stop_queue.put(1)
    except KeyboardInterrupt:
        # processing aborts in spite of not acting to the KeyboardInterrupt
        pass


def _exec_asset_handler(handler: Callable, asset_name: str, ctx: AssetCtx) -> None:
    cli.info(f"running asset {asset_name} handler")
    try:
        with cwd(ctx.config.project_root):
            handler(ctx)
    except Exception:
        cli.pp_exc()
        cli.pp_err_details(
            "error executing handler function", {}
        )
        raise ConsumerProcessFatalError


def _asset_compile_process_inner(queue: mp.Queue, cfg: config.Config) -> None:
    handlers = {}
    # TODO: handle changes IN handlers.. (reload this process)
    # For each handler, import and resolve its handler function
    for asset_name, asset_opts in cfg.assets.items():
        if not "handler" in asset_opts:
            raise RuntimeError("program error - config validation should ensure handler string exists")
        elif len(asset_opts["handler"].split(":")) != 2:
            raise RuntimeError("program error - config must ensure handler strings are properly formatted")
        handler_module, handler_fn = asset_opts["handler"].split(":")
        mod = importlib.import_module(handler_module)
        if not hasattr(mod, handler_fn):
            raise AssetHandlerNotFoundError(
                asset_name, asset_opts["dir"], asset_opts["handler"],
                handler_fn, handler_module, mod.__file__
            )
        handler = getattr(mod, handler_fn)
        if not callable(handler):
            raise AssetHandlerNotCallableError(
                asset_name, asset_opts["dir"], asset_opts["handler"],
                handler_fn, handler_module, mod.__file__
            )
        handlers[asset_name] = handler

    # trigger a once-over compile
    for asset_name, handler in handlers.items():
        ctx = AssetCtx(config=cfg, asset_dir=cfg.assets[asset_name]["dir"], dev_mode=cfg.dev_mode)
        _exec_asset_handler(handler, asset_name, ctx)
    while True:
        event = queue.get(block=True)
        action = event["type"]
        if action == EventType.ASSET_CHANGED:
            asset_name = event["payload"]["asset_name"]
            handler = handlers[asset_name]
            opts = event["payload"]["asset_opts"]
            ctx = AssetCtx(config=cfg, asset_dir=opts["dir"],
                           file=Path(event["payload"]["file"]), dev_mode=cfg.dev_mode)
            _exec_asset_handler(handler, asset_name, ctx)
        elif action == EventType.STOP:
            return


def _asset_compile_process(queue: mp.Queue, stop_queue: mp.Queue, cfg: config.Config) -> None:
    try:
        _asset_compile_process_inner(queue, cfg)
    except KeyboardInterrupt:
        pass
    except ConsumerProcessFatalError:
        stop_queue.put(1)
    except AssetHandlerNotFoundError as e:
        cli.pp_exc()
        cli.pp_err_details(str(e), {
            "asset": e.asset_name,
            "dir": e.asset_path,
            "handler": e.handler,
            "module file": e.handler_module_fpath,
            "module": e.handler_module,
            "handler fn": e.handler_fn
        })
        # warn master process that an unhandled exception occurred
        stop_queue.put(1)
    except AssetHandlerNotCallableError as e:
        cli.pp_exc()
        cli.pp_err_details(
            f"the symbol pointed to by {e.handler} is not a callable - must be a function/object implementing __call__",
            {
                "asset": e.asset_name,
                "dir": e.asset_path,
                "handler": e.handler,
                "module file": e.handler_module_fpath,
                "module": e.handler_module,
                "handler fn": e.handler_fn
            })
        # warn master process that an unhandled exception occurred
        stop_queue.put(1)
    except Exception:
        cli.pp_exc()
        cli.pp_err_details("unhandled exception!", {})
        # warn master process that an unhandled exception occurred
        stop_queue.put(1)


def compile_watch(cfg: config.Config) -> None:
    if not isinstance(cfg, config.Config):
        raise RuntimeError(f"expected Config, got {type(cfg)}")
    ctx = mp.get_context("spawn")
    page_queue = ctx.Queue()
    asset_queue = ctx.Queue()

    observer = Observer()
    observer.schedule(
        PageHandler(page_queue),
        str(cfg.pages_path.absolute()),
        recursive=True
    )
    observer.schedule(
        ContextCodeHandler(page_queue),
        str(cfg.code.module_path),
        recursive=True
    )
    observer.schedule(
        TemplateEventHandler(page_queue),
        str(cfg.templates_path.absolute()),
        recursive=True
    )
    for asset_name, asset_opts in cfg.assets.items():
        print(f"""{colors.B_MAGENTA}> {colors.B_WHITE}asset watcher {colors.B_MAGENTA}{asset_name}{colors.B_WHITE} (dir: {colors.B_MAGENTA}{asset_opts["dir"]}{colors.B_WHITE})""")
        observer.schedule(
            AssetEventHandler(asset_queue, asset_name, asset_opts),
            str(asset_opts["dir"]),
            recursive=True
        )
    observer.start()

    stop_queue = ctx.Queue()
    p_handles: Dict[int, ConsumerProcess] = {}
    # Start compile processes.
    #
    # Compilation is split into 2 processes:
    # 1) Page compiler
    #   This process compiles pages - compiling single- or all pages as needed.
    #   If a page changes: recompile the page
    #   If a template changes: recompile all pages
    #   If the user-code changes: restart process, recompile all pages
    # 2) Assets "compiler"
    #   Associate a user-defined handler function with a directory.
    #   When the compiler starts, each handler is triggered with the file-argument being unset - this means the handler
    #   should apply to all files in the asset directory.
    #
    #   The same applies in case of a one-time compile being triggered. In case of being in a development/watch-mode
    #   loop, the function is first triggered without a file argument (meaning: apply operation to all files) and THEN
    #   triggered each time a file is modified.
    for cp in [
        ConsumerProcess(target=_compile_process, input_queue=page_queue, args=(stop_queue, cfg)),
        ConsumerProcess(target=_asset_compile_process, input_queue=asset_queue, args=(stop_queue, cfg))
    ]:
        p = cp.spawn(ctx=ctx)
        p.start()
        p_handles[p.sentinel] = cp

    p_quit: List[int] = []
    while stop_queue.empty():
        for sentinel in p_quit:
            cp = p_handles[sentinel]
            del p_handles[sentinel]
            p_new = cp.spawn(ctx=ctx)
            p_new.start()
            p_handles[p_new.sentinel] = cp

        # block until one or more processes exit - provided the stop_queue is
        # empty, we will process and restart them in the next loop iteration.
        p_quit = mp_wait(p_handles.keys())

    for cp in [v for k, v in p_handles.items() if k not in set(p_quit)]:
        cp.stop()


def compile_once(cfg: config.Config) -> None:
    # We setup both processes as in watch-mode, execute them and immediately
    # afterwards send a STOP message which they will obey as soon as they would
    # enter watch-mode.
    #
    # Doing this ensures both compile steps behave similarly and cuts down on
    # code duplication.
    ctx = mp.get_context("spawn")
    page_queue = ctx.Queue()
    asset_queue = ctx.Queue()
    stop_queue = ctx.Queue()
    processes = [
        ConsumerProcess(target=_compile_process, input_queue=page_queue, args=(stop_queue, cfg)),
        ConsumerProcess(target=_asset_compile_process, input_queue=asset_queue, args=(stop_queue, cfg))
    ]
    for cp in processes:
        p = cp.spawn(ctx=ctx)
        p.start()
    # avoid a race condition error from the runtime itself
    time.sleep(1)
    for cp in processes:
        cp.stop()
