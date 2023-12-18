import os
import shutil
import click
import subprocess
import pkg_resources
from rich.console import Console

console = Console()


@click.group()
def cli():
    pass


@cli.command()
@click.option("--template", default="fly.io", help="The template to use.")
@click.argument("extra_args", nargs=-1, type=click.UNPROCESSED)
def create(template, extra_args):
    try:
        # Determine the installation location of the embedchain package
        package_path = pkg_resources.resource_filename("embedchain", "")
    except ImportError:
        console.print("❌ [bold red]Failed to locate the 'embedchain' package. Is it installed?[/bold red]")
        return

    # Construct the source path from the embedchain package
    src_path = os.path.join(package_path, "deployment", template)

    if not os.path.exists(src_path):
        console.print(f"❌ [bold red]Template '{template}' not found.[/bold red]")
        return

    shutil.copytree(src_path, os.getcwd(), dirs_exist_ok=True)
    console.print(f"✅ [bold green]Successfully created app from template '{template}'.[/bold green]")

    fly_launch_command = ["fly", "launch", "--region", "sjc"] + list(extra_args)
    try:
        console.print(f"🚀 [bold cyan]Running: {' '.join(fly_launch_command)}[/bold cyan]")
        subprocess.run(fly_launch_command, check=True)
        console.print("✅ [bold green]'fly launch' executed successfully.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except FileNotFoundError:
        console.print(
            "❌ [bold red]'fly' command not found. Please ensure Fly CLI is installed and in your PATH.[/bold red]"
        )


@cli.command()
@click.option("--debug", is_flag=True, help="Enable or disable debug mode.")
@click.option("--host", default="127.0.0.1", help="The host address to run the FastAPI app on.")
@click.option("--port", default=8000, help="The port to run the FastAPI app on.")
def dev(debug, host, port):
    uvicorn_command = ["uvicorn", "app:app"]

    if debug:
        uvicorn_command.append("--reload")

    uvicorn_command.extend(["--host", host, "--port", str(port)])

    try:
        console.print(f"🚀 [bold cyan]Running FastAPI app with command: {' '.join(uvicorn_command)}[/bold cyan]")
        subprocess.run(uvicorn_command, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except KeyboardInterrupt:
        console.print("\n🛑 [bold yellow]FastAPI server stopped[/bold yellow]")


@cli.command()
def deploy():
    deploy_command = ["fly", "deploy"]
    try:
        console.print(f"🚀 [bold cyan]Running: {' '.join(deploy_command)}[/bold cyan]")
        subprocess.run(deploy_command, check=True)
        console.print("✅ [bold green]'fly deploy' executed successfully.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except FileNotFoundError:
        console.print(
            "❌ [bold red]'fly' command not found. Please ensure Fly CLI is installed and in your PATH.[/bold red]"
        )
