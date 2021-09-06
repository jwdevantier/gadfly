import signal
import sys
from pathlib import Path
from multiprocessing import Process

import typer
from livereload import Server

from gadfly import config
from gadfly import mp

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
    mp.compile_once(config.config)


@app.command()
def watch(watch_port: int = 5500):
    """
    Watch for changes and recompile when needed.
    """
    def _serve():
        Server().serve(root=config.config.output_path, port=watch_port)

    server = Process(target=_serve)

    def on_ctrl_c(sig, frame):
        print("CTRL-C hit..")
        server.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_ctrl_c)

    server.start()
    mp.compile_watch(config.config)
    server.terminate()


@app.callback()
def main(silent: bool = False, project: Path = typer.Option(default=Path("."), help="project directory")):
    config.config = config.Config(
        silent=silent,
        project_root=project.absolute(),
        context={}, page_md={}
    )


if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    app()
