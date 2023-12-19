import re
import os
import shutil
import subprocess

import click
import pkg_resources
from rich.console import Console

console = Console()


@click.group()
def cli():
    pass


def setup_fly_io_app(extra_args):
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


def setup_modal_com_app(extra_args):
    modal_setup_file = os.path.join(os.path.expanduser("~"), ".modal.toml")
    if os.path.exists(modal_setup_file):
        console.print(
            """✅ [bold green]Modal setup already done. You can now install the dependencies by doing \n
            `pip install -r requirements.txt`[/bold green]"""
        )
        return
    modal_setup_cmd = ["modal", "setup"] + list(extra_args)
    console.print(f"🚀 [bold cyan]Running: {' '.join(modal_setup_cmd)}[/bold cyan]")
    subprocess.run(modal_setup_cmd, check=True)
    shutil.move(".env.example", ".env")
    console.print("Great! Now you can install the dependencies by doing `pip install -r requirements.txt`")


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

    if template == "fly.io":
        setup_fly_io_app(extra_args)
    elif template == "modal.com":
        setup_modal_com_app(extra_args)
    else:
        raise ValueError(f"Unknown template '{template}'.")


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


def read_env_file(env_file_path):
    """
    Reads an environment file and returns a dictionary of key-value pairs.

    Args:
    env_file_path (str): The path to the .env file.

    Returns:
    dict: Dictionary of environment variables.
    """
    env_vars = {}
    with open(env_file_path, "r") as file:
        for line in file:
            # Ignore comments and empty lines
            if line.strip() and not line.strip().startswith("#"):
                # Assume each line is in the format KEY=VALUE
                key_value_match = re.match(r"(\w+)=(.*)", line.strip())
                if key_value_match:
                    key, value = key_value_match.groups()
                    env_vars[key] = value
    return env_vars


def deploy_fly():
    app_name = ""
    with open("fly.toml", "r") as file:
        for line in file:
            if line.strip().startswith("app ="):
                app_name = line.split("=")[1].strip().strip('"')

    if not app_name:
        console.print("❌ [bold red]App name not found in fly.toml[/bold red]")
        return

    env_vars = read_env_file(".env")
    secrets_command = ["flyctl", "secrets", "set", "-a", app_name] + [f"{k}={v}" for k, v in env_vars.items()]

    deploy_command = ["fly", "deploy"]
    try:
        # Set secrets
        console.print(f"🔐 [bold cyan]Setting secrets for {app_name}[/bold cyan]")
        subprocess.run(secrets_command, check=True)

        # Deploy application
        console.print(f"🚀 [bold cyan]Running: {' '.join(deploy_command)}[/bold cyan]")
        subprocess.run(deploy_command, check=True)
        console.print("✅ [bold green]'fly deploy' executed successfully.[/bold green]")

    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except FileNotFoundError:
        console.print(
            "❌ [bold red]'fly' command not found. Please ensure Fly CLI is installed and in your PATH.[/bold red]"
        )


@cli.command()
def deploy():
    # Check for platform-specific files
    if os.path.exists("fly.toml"):
        deploy_fly()
    # Add elif conditions here for other platforms
    else:
        console.print("❌ [bold red]No recognized deployment platform found.[/bold red]")
