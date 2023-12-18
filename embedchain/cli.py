import os
import shutil
import click
import subprocess
from rich.console import Console

console = Console()


@click.group()
def cli():
    pass


@cli.command()
@click.option("--template", default="fly.io", help="The template to use.")
@click.argument("app_name")
def create(template, app_name):
    src_path = os.path.join("embedchain", "deployment", template)
    dest_path = app_name

    # Check if the source directory exists
    if not os.path.exists(src_path):
        console.print(f"❌ [bold red]Template '{template}' not found.[/bold red]")
        return

    # Create destination directory if it doesn't exist
    os.makedirs(dest_path, exist_ok=True)

    # Copy the directory
    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)

    # Print a success message
    console.print(f"✅ [bold green]Successfully created '{app_name}' from template '{template}'.[/bold green]")

    # Run the fly launch command
    try:
        console.print("🚀 [bold cyan]Running 'fly launch --no-deploy --region sjc'...[/bold cyan]")
        subprocess.run(["fly", "launch", "--no-deploy", "--region", "sjc"], check=True)
        console.print("✅ [bold green]'fly launch --no-deploy' executed successfully.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred while running 'fly launch --no-deploy': {e}[/bold red]")
    except FileNotFoundError:
        console.print(
            "❌ [bold red]'fly' command not found. Please ensure Fly CLI is installed and in your PATH.[/bold red]"
        )
    # Suggest the user to change directory
    console.print(f"🔗 [bold]Run 'cd {dest_path}' to switch to the new project directory.[/bold]")


@cli.command()
@click.option("--debug", is_flag=True, help="Enable or disable debug mode.")
@click.option("--host", default="127.0.0.1", help="The host address to run Flask on.")
@click.option("--port", default=5000, help="The port to run Flask on.")
def dev(debug, host, port):
    flask_command = ["flask", "--app", "app", "run"]

    if debug:
        flask_command.append("--debug")

    flask_command.extend(["--host", host, "--port", str(port)])

    try:
        console.print(f"🚀 [bold cyan]Running Flask app with command: {' '.join(flask_command)}[/bold cyan]")
        subprocess.run(flask_command, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except KeyboardInterrupt:
        console.print("\n🛑 [bold yellow]Flask server stopped[/bold yellow]")
