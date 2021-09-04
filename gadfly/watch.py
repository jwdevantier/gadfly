from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, EVENT_TYPE_CLOSED, FileSystemMovedEvent
from watchdog import events
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import time
from gadfly import config
from gadfly.context import update_context
from gadfly import compiler
from gadfly.utils import info
from hashlib import sha256


class WatcherState(Enum):
    STOPPED = 0
    RUNNING = 1


class EventType:
    # Not a true enum, that would break the interface
    CLOSED = events.EVENT_TYPE_CLOSED
    MOVED = events.EVENT_TYPE_MOVED
    CREATED = events.EVENT_TYPE_CREATED
    DELETED = events.EVENT_TYPE_DELETED
    MODIFIED = events.EVENT_TYPE_MODIFIED


@dataclass
class Watcher:
    handler: FileSystemEventHandler
    path: Path
    observer: Observer = field(default_factory=lambda: Observer())
    recursive: bool = True

    def __post_init__(self):
        self._state = WatcherState.STOPPED
        self._keep_running = True

    def run(self):
        if not self._state == WatcherState.STOPPED:
            raise RuntimeError(f"cannot start a running watcher")
        self.observer.schedule(
            self.handler, str(self.path.absolute()), recursive=self.recursive
        )
        self.observer.start()
        self._keep_running = True
        self._state = WatcherState.RUNNING

    def join(self):
        if not self._state == WatcherState.RUNNING:
            raise RuntimeError(f"watcher not running")
        try:
            while self._keep_running:
                time.sleep(1)
        except Exception as e:
            raise e
        finally:
            if self._state == WatcherState.RUNNING:
                self._state = WatcherState.STOPPED
                self.observer.stop()

    def stop(self):
        self._keep_running = False
        self.join()


# compute relpath (rel to root src dir)
# *if* a md file - infer corresponding dst path
#   - if moved: rm old compiled output, recompile
#   - if modified: recompile
#   - if deleted: remove old compiled output
def is_page(event: FileSystemEvent) -> bool:
    return ((not event.is_directory)
            and event.src_path.endswith(".md"))


def delete_output(path: Path):
    path.unlink(missing_ok=True)
    if path.name == "index.html":
        # will error out if dir is not empty, that's OK.
        # TODO: test, capture error and print relevant message
        path.parent.rmdir()


def compile_page(path: Path):
    info(f"recompile {Path(path).relative_to(config.config.pages_path)}")
    compiler.render(config.config, path)


def file_sha256(fpath: Path) -> str:
    with open(fpath, "rb") as fh:
        return sha256(fh.read()).hexdigest()


@dataclass(frozen=True)
class CompileHandler(FileSystemEventHandler):

    def on_deleted(self, event: FileSystemEvent):
        """Delete corresponding compiled page"""
        if not is_page(event):
            return
        outpath = compiler.output_path(config.config, Path(event.src_path))
        delete_output(outpath)

    def on_moved(self, event: FileSystemMovedEvent):
        """Trigger delete"""
        if not is_page(event):
            return
        delete_output(compiler.output_path(
            config.config,
            Path(event.src_path)
        ))
        compile_page(Path(event.dest_path))

    def on_modified(self, event: FileSystemEvent):
        if not is_page(event):
            return
        compile_page(Path(event.src_path))


class ContextEventHandler(FileSystemEventHandler):
    def __init__(self):
        self._db = {}

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or not event.src_path.endswith(".py"):
            return
        hash = self._db.get(event.src_path)
        current_hash = file_sha256(event.src_path)
        if hash == current_hash:
                return
        self._db[event.src_path] = current_hash
        print(f"<> {event.src_path} {event.event_type}")
        update_context(config.config)
        compiler.render_all(config.config)


@dataclass(frozen=True)
class TemplateEventHandler(FileSystemEventHandler):
    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        print(f"<> {event.src_path} {event.event_type}")
        compiler.render_all(config.config)
