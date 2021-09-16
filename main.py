import signal
import sys
from pathlib import Path
from multiprocessing import Process

import typer
from livereload import Server
import toml

from gadfly import config
from gadfly import mp
from gadfly import cli
from gadfly import genproject

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
    # TODO: for most commands, we would want to check and enforce that the project directory exists
    #       maybe a decorator ?
    # install project directory as a path we look for modules in
    # this permits handlers to be expressed as strings of the form "mod1.mod2:fn"
    sys.path.insert(1, str(project.absolute()))
    conf_path = project.absolute() / "gadfly.toml"
    if not conf_path.exists():
        print(f"No {conf_path.name} in {conf_path.parent}.")
        if cli.prompt_yes_no("Create 'gadfly.toml' ?"):
            genproject.genconf(conf_path)
        else:
            print("oh... OK...")
            return

    try:
        conf_dict = toml.load(conf_path)
    except toml.TomlDecodeError:
        cli.pp_exc()
        cli.pp_err_details(f"Failed to read TOML config, invalid syntax", {
            "Project": (Path.cwd() / conf_path).parent,
            "File": (Path.cwd() / conf_path).name,
        })
        sys.exit(1)
    config.config = config.read_config(project.absolute(), conf_dict)
    config.config.silent = silent


if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    app()
