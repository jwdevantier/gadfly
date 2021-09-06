import multiprocessing as mp
from importlib.util import spec_from_file_location, module_from_spec
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileSystemMovedEvent
from pathlib import Path
from gadfly.utils import *
from gadfly import config
from gadfly import compiler
from queue import Empty as QueueEmpty


class EventType:
    CONTEXT_CHANGED = "context_changed"
    PAGE_CHANGED = "page_changed"
    TEMPLATE_CHANGED = "template_changed"
    STOP = "stop"


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


def _eval_context(cfg: config.Config):
    # NOTE: _must_ be run within the context of a separate process.
    #       Otherwise, changes to modules would never take effect as the import
    #       system caches imports.
    fpath = cfg.context_main_file
    spec = spec_from_file_location("module.name", fpath)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main(cfg)


def _compile_process_inner(queue: mp.Queue, stop_queue: mp.Queue, cfg: config.Config) -> None:
    # this globally assigned variable is not set in the new process.
    config.config = cfg
    # (re-)compute context, done once for duration of the compile-process' lifetime.
    cfg.context = _eval_context(cfg)
    # render all pages using the newly computed context.
    compiler.render_all(cfg)
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
                compiler.render(cfg, Path(page))
        elif action == EventType.TEMPLATE_CHANGED:
            compiler.render_all(cfg)
        elif action == EventType.CONTEXT_CHANGED:
            return
        else:
            raise RuntimeError("unknown action")

        if event["type"] == EventType.STOP:
            stop_queue.put(True)
            return


def _compile_process(queue: mp.Queue, stop_queue: mp.Queue, cfg: config.Config) -> None:
    try:
        _compile_process_inner(queue, stop_queue, cfg)
    except KeyboardInterrupt:
        # processing aborts in spite of not acting to the KeyboardInterrupt
        pass


def compile_watch(cfg: config.Config) -> None:
    if not isinstance(cfg, config.Config):
        raise RuntimeError(f"expected Config, got {type(cfg)}")
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()

    observer = Observer()
    observer.schedule(
        PageHandler(queue),
        str(cfg.pages_path.absolute()),
        recursive=True
    )
    observer.schedule(
        ContextCodeHandler(queue),
        str(cfg.context_files_path.absolute()),
        recursive=True
    )
    observer.schedule(
        TemplateEventHandler(queue),
        str(cfg.templates_path.absolute()),
        recursive=True
    )
    observer.start()

    stop_queue = ctx.Queue()
    # TODO ctrl-c support
    while stop_queue.empty():
        p = ctx.Process(target=_compile_process, args=(queue, stop_queue, cfg))
        p.start()
        p.join()


def compile_once(cfg: config.Config) -> None:
    if not isinstance(cfg, config.Config):
        raise RuntimeError(f"expected Config, got {type(cfg)}")
    config.context = _eval_context(cfg)
    # render all pages using the newly computed context.
    compiler.render_all(cfg)


# TODO: write CompileProcess instance
#           This will loop on the queue (abort and stop all watchers on CTRL-C)
#           And it will spawn a PROCESS each time a compile is required.
#           Because we cannot pass fn's any other way -- recompute context on each compile FORK
#           Pass arg indicating which file to recompile, None to recompile ALL
#
#           Ahead of compile, attempt emptying the queue, doing pre-event work for each event
#           Ahead of scheduling the compile.
#           THEN compile  -- THIS CUTS DOWN ON NUMBER OF COMPILE RUNS