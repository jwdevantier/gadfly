import signal
import sys
from pathlib import Path

import typer
from livereload import Server

from gadfly import compiler
from gadfly import config
from gadfly.context import update_context
from gadfly.watch import Watcher, CompileHandler, ContextEventHandler, TemplateEventHandler
from gadfly.utils import info

# CLI
#  watch+dev server
#  single compile pass
app = typer.Typer(
    help="Static site generator"
)


@app.command()
def compile():
    """
    Do a single compile.
    """
    print("compiling")
    update_context(config.config)
    print("-- context --")
    print(repr(config.config.context))
    print("-- -- --")
    compiler.render_all(config.config)


@app.command()
def watch():
    """
    Watch for changes and recompile when needed.
    """
    update_context(config.config)
    compiler.render_all(config.config)

    info("watching for changes...")
    pages_watcher = Watcher(
        path=config.config.pages_path, handler=CompileHandler())
    pages_watcher.run()

    context_watcher = Watcher(
        path=config.config.context_files_path,
        handler=ContextEventHandler()
    )
    context_watcher.run()

    template_watcher = Watcher(
        path=config.config.templates_path,
        handler=TemplateEventHandler()
    )
    template_watcher.run()

    server = Server()

    def on_ctrl_c(sig, frame):
        pages_watcher.stop()
        context_watcher.stop()
        template_watcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_ctrl_c)

    server.serve(root=config.config.output_path)


@app.callback()
def main(silent: bool = False, project: Path = typer.Option(default=Path("."), help="project directory")):
    config.config = config.Config(
        silent=silent,
        project_root=project.absolute(),
        context={}
    )


if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    app()
