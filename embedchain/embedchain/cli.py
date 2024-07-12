import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import click
import requests
from rich.console import Console

from embedchain.telemetry.posthog import AnonymousTelemetry
from embedchain.utils.cli import (deploy_fly, deploy_gradio_app,
                                  deploy_hf_spaces, deploy_modal,
                                  deploy_render, deploy_streamlit,
                                  get_pkg_path_from_name, setup_fly_io_app,
                                  setup_gradio_app, setup_hf_app,
                                  setup_modal_com_app, setup_render_com_app,
                                  setup_streamlit_io_app)

console = Console()
api_process = None
ui_process = None

anonymous_telemetry = AnonymousTelemetry()


def signal_handler(sig, frame):
    """Signal handler to catch termination signals and kill server processes."""
    global api_process, ui_process
    console.print("\n🛑 [bold yellow]Stopping servers...[/bold yellow]")
    if api_process:
        api_process.terminate()
        console.print("🛑 [bold yellow]API server stopped.[/bold yellow]")
    if ui_process:
        ui_process.terminate()
        console.print("🛑 [bold yellow]UI server stopped.[/bold yellow]")
    sys.exit(0)


@click.group()
def cli():
    pass


@cli.command()
@click.argument("app_name")
@click.option("--docker", is_flag=True, help="Use docker to create the app.")
@click.pass_context
def create_app(ctx, app_name, docker):
    if Path(app_name).exists():
        console.print(
            f"❌ [red]Directory '{app_name}' already exists. Try using a new directory name, or remove it.[/red]"
        )
        return

    os.makedirs(app_name)
    os.chdir(app_name)

    # Step 1: Download the zip file
    zip_url = "http://github.com/embedchain/ec-admin/archive/main.zip"
    console.print(f"Creating a new embedchain app in [green]{Path().resolve()}[/green]\n")
    try:
        response = requests.get(zip_url)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(response.content)
            zip_file_path = tmp_file.name
        console.print("✅ [bold green]Fetched template successfully.[/bold green]")
    except requests.RequestException as e:
        console.print(f"❌ [bold red]Failed to download zip file: {e}[/bold red]")
        anonymous_telemetry.capture(event_name="ec_create_app", properties={"success": False})
        return

    # Step 2: Extract the zip file
    try:
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            # Get the name of the root directory inside the zip file
            root_dir = Path(zip_ref.namelist()[0])
            for member in zip_ref.infolist():
                # Build the path to extract the file to, skipping the root directory
                target_file = Path(member.filename).relative_to(root_dir)
                source_file = zip_ref.open(member, "r")
                if member.is_dir():
                    # Create directory if it doesn't exist
                    os.makedirs(target_file, exist_ok=True)
                else:
                    with open(target_file, "wb") as file:
                        # Write the file
                        shutil.copyfileobj(source_file, file)
            console.print("✅ [bold green]Extracted zip file successfully.[/bold green]")
            anonymous_telemetry.capture(event_name="ec_create_app", properties={"success": True})
    except zipfile.BadZipFile:
        console.print("❌ [bold red]Error in extracting zip file. The file might be corrupted.[/bold red]")
        anonymous_telemetry.capture(event_name="ec_create_app", properties={"success": False})
        return

    if docker:
        subprocess.run(["docker-compose", "build"], check=True)
    else:
        ctx.invoke(install_reqs)


@cli.command()
def install_reqs():
    try:
        console.print("Installing python requirements...\n")
        time.sleep(2)
        os.chdir("api")
        subprocess.run(["pip", "install", "-r", "requirements.txt"], check=True)
        os.chdir("..")
        console.print("\n ✅ [bold green]Installed API requirements successfully.[/bold green]\n")
    except Exception as e:
        console.print(f"❌ [bold red]Failed to install API requirements: {e}[/bold red]")
        anonymous_telemetry.capture(event_name="ec_install_reqs", properties={"success": False})
        return

    try:
        os.chdir("ui")
        subprocess.run(["yarn"], check=True)
        console.print("\n✅ [bold green]Successfully installed frontend requirements.[/bold green]")
        anonymous_telemetry.capture(event_name="ec_install_reqs", properties={"success": True})
    except Exception as e:
        console.print(f"❌ [bold red]Failed to install frontend requirements. Error: {e}[/bold red]")
        anonymous_telemetry.capture(event_name="ec_install_reqs", properties={"success": False})


@cli.command()
@click.option("--docker", is_flag=True, help="Run inside docker.")
def start(docker):
    if docker:
        subprocess.run(["docker-compose", "up"], check=True)
        return

    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Step 1: Start the API server
    try:
        os.chdir("api")
        api_process = subprocess.Popen(["python", "-m", "main"], stdout=None, stderr=None)
        os.chdir("..")
        console.print("✅ [bold green]API server started successfully.[/bold green]")
    except Exception as e:
        console.print(f"❌ [bold red]Failed to start the API server: {e}[/bold red]")
        anonymous_telemetry.capture(event_name="ec_start", properties={"success": False})
        return

    # Sleep for 2 seconds to give the user time to read the message
    time.sleep(2)

    # Step 2: Install UI requirements and start the UI server
    try:
        os.chdir("ui")
        subprocess.run(["yarn"], check=True)
        ui_process = subprocess.Popen(["yarn", "dev"])
        console.print("✅ [bold green]UI server started successfully.[/bold green]")
        anonymous_telemetry.capture(event_name="ec_start", properties={"success": True})
    except Exception as e:
        console.print(f"❌ [bold red]Failed to start the UI server: {e}[/bold red]")
        anonymous_telemetry.capture(event_name="ec_start", properties={"success": False})

    # Keep the script running until it receives a kill signal
    try:
        api_process.wait()
        ui_process.wait()
    except KeyboardInterrupt:
        console.print("\n🛑 [bold yellow]Stopping server...[/bold yellow]")


@cli.command()
@click.option("--template", default="fly.io", help="The template to use.")
@click.argument("extra_args", nargs=-1, type=click.UNPROCESSED)
def create(template, extra_args):
    anonymous_telemetry.capture(event_name="ec_create", properties={"template_used": template})
    template_dir = template
    if "/" in template_dir:
        template_dir = template.split("/")[1]
    src_path = get_pkg_path_from_name(template_dir)
    shutil.copytree(src_path, os.getcwd(), dirs_exist_ok=True)
    console.print(f"✅ [bold green]Successfully created app from template '{template}'.[/bold green]")

    if template == "fly.io":
        setup_fly_io_app(extra_args)
    elif template == "modal.com":
        setup_modal_com_app(extra_args)
    elif template == "render.com":
        setup_render_com_app()
    elif template == "streamlit.io":
        setup_streamlit_io_app()
    elif template == "gradio.app":
        setup_gradio_app()
    elif template == "hf/gradio.app" or template == "hf/streamlit.io":
        setup_hf_app()
    else:
        raise ValueError(f"Unknown template '{template}'.")

    embedchain_config = {"provider": template}
    with open("embedchain.json", "w") as file:
        json.dump(embedchain_config, file, indent=4)
        console.print(
            f"🎉 [green]All done! Successfully created `embedchain.json` with '{template}' as provider.[/green]"
        )


def run_dev_fly_io(debug, host, port):
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


def run_dev_modal_com():
    modal_run_cmd = ["modal", "serve", "app"]
    try:
        console.print(f"🚀 [bold cyan]Running FastAPI app with command: {' '.join(modal_run_cmd)}[/bold cyan]")
        subprocess.run(modal_run_cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except KeyboardInterrupt:
        console.print("\n🛑 [bold yellow]FastAPI server stopped[/bold yellow]")


def run_dev_streamlit_io():
    streamlit_run_cmd = ["streamlit", "run", "app.py"]
    try:
        console.print(f"🚀 [bold cyan]Running Streamlit app with command: {' '.join(streamlit_run_cmd)}[/bold cyan]")
        subprocess.run(streamlit_run_cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except KeyboardInterrupt:
        console.print("\n🛑 [bold yellow]Streamlit server stopped[/bold yellow]")


def run_dev_render_com(debug, host, port):
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


def run_dev_gradio():
    gradio_run_cmd = ["gradio", "app.py"]
    try:
        console.print(f"🚀 [bold cyan]Running Gradio app with command: {' '.join(gradio_run_cmd)}[/bold cyan]")
        subprocess.run(gradio_run_cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except KeyboardInterrupt:
        console.print("\n🛑 [bold yellow]Gradio server stopped[/bold yellow]")


@cli.command()
@click.option("--debug", is_flag=True, help="Enable or disable debug mode.")
@click.option("--host", default="127.0.0.1", help="The host address to run the FastAPI app on.")
@click.option("--port", default=8000, help="The port to run the FastAPI app on.")
def dev(debug, host, port):
    template = ""
    with open("embedchain.json", "r") as file:
        embedchain_config = json.load(file)
        template = embedchain_config["provider"]

    anonymous_telemetry.capture(event_name="ec_dev", properties={"template_used": template})
    if template == "fly.io":
        run_dev_fly_io(debug, host, port)
    elif template == "modal.com":
        run_dev_modal_com()
    elif template == "render.com":
        run_dev_render_com(debug, host, port)
    elif template == "streamlit.io" or template == "hf/streamlit.io":
        run_dev_streamlit_io()
    elif template == "gradio.app" or template == "hf/gradio.app":
        run_dev_gradio()
    else:
        raise ValueError(f"Unknown template '{template}'.")


@cli.command()
def deploy():
    # Check for platform-specific files
    template = ""
    ec_app_name = ""
    with open("embedchain.json", "r") as file:
        embedchain_config = json.load(file)
        ec_app_name = embedchain_config["name"] if "name" in embedchain_config else None
        template = embedchain_config["provider"]

    anonymous_telemetry.capture(event_name="ec_deploy", properties={"template_used": template})
    if template == "fly.io":
        deploy_fly()
    elif template == "modal.com":
        deploy_modal()
    elif template == "render.com":
        deploy_render()
    elif template == "streamlit.io":
        deploy_streamlit()
    elif template == "gradio.app":
        deploy_gradio_app()
    elif template.startswith("hf/"):
        deploy_hf_spaces(ec_app_name)
    else:
        console.print("❌ [bold red]No recognized deployment platform found.[/bold red]")
