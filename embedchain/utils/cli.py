import os
import re
import shutil
import subprocess

import pkg_resources
from rich.console import Console

console = Console()


def get_pkg_path_from_name(template: str):
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

    return src_path


def setup_fly_io_app(extra_args):
    fly_launch_command = ["fly", "launch", "--region", "sjc", "--no-deploy"] + list(extra_args)
    try:
        console.print(f"🚀 [bold cyan]Running: {' '.join(fly_launch_command)}[/bold cyan]")
        shutil.move(".env.example", ".env")
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
    else:
        modal_setup_cmd = ["modal", "setup"] + list(extra_args)
        console.print(f"🚀 [bold cyan]Running: {' '.join(modal_setup_cmd)}[/bold cyan]")
        subprocess.run(modal_setup_cmd, check=True)
    shutil.move(".env.example", ".env")
    console.print(
        """Great! Now you can install the dependencies by doing: \n
                  `pip install -r requirements.txt`\n
                  \n
                  To run your app locally:\n
                  `ec dev`
                  """
    )


def setup_render_com_app():
    render_setup_file = os.path.join(os.path.expanduser("~"), ".render/config.yaml")
    if os.path.exists(render_setup_file):
        console.print(
            """✅ [bold green]Render setup already done. You can now install the dependencies by doing \n
            `pip install -r requirements.txt`[/bold green]"""
        )
    else:
        render_setup_cmd = ["render", "config", "init"]
        console.print(f"🚀 [bold cyan]Running: {' '.join(render_setup_cmd)}[/bold cyan]")
        subprocess.run(render_setup_cmd, check=True)
    shutil.move(".env.example", ".env")
    console.print(
        """Great! Now you can install the dependencies by doing: \n
                  `pip install -r requirements.txt`\n
                  \n
                  To run your app locally:\n
                  `ec dev`
                  """
    )


def setup_streamlit_io_app():
    # nothing needs to be done here
    console.print("Great! Now you can install the dependencies by doing `pip install -r requirements.txt`")


def setup_gradio_app():
    # nothing needs to be done here
    console.print("Great! Now you can install the dependencies by doing `pip install -r requirements.txt`")


def setup_hf_app():
    subprocess.run(["pip", "install", "huggingface_hub[cli]"], check=True)
    hf_setup_file = os.path.join(os.path.expanduser("~"), ".cache/huggingface/token")
    if os.path.exists(hf_setup_file):
        console.print(
            """✅ [bold green]HuggingFace setup already done. You can now install the dependencies by doing \n
            `pip install -r requirements.txt`[/bold green]"""
        )
    else:
        console.print(
            """🚀 [cyan]Running: huggingface-cli login \n
                Please provide a [bold]WRITE[/bold] token so that we can directly deploy\n
                your apps from the terminal.[/cyan]
                """
        )
        subprocess.run(["huggingface-cli", "login"], check=True)
    console.print("Great! Now you can install the dependencies by doing `pip install -r requirements.txt`")


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


def deploy_modal():
    modal_deploy_cmd = ["modal", "deploy", "app"]
    try:
        console.print(f"🚀 [bold cyan]Running: {' '.join(modal_deploy_cmd)}[/bold cyan]")
        subprocess.run(modal_deploy_cmd, check=True)
        console.print("✅ [bold green]'modal deploy' executed successfully.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except FileNotFoundError:
        console.print(
            "❌ [bold red]'modal' command not found. Please ensure Modal CLI is installed and in your PATH.[/bold red]"
        )


def deploy_streamlit():
    streamlit_deploy_cmd = ["streamlit", "run", "app.py"]
    try:
        console.print(f"🚀 [bold cyan]Running: {' '.join(streamlit_deploy_cmd)}[/bold cyan]")
        console.print(
            """\n\n✅ [bold yellow]To deploy a streamlit app, you can directly it from the UI.\n
        Click on the 'Deploy' button on the top right corner of the app.\n
        For more information, please refer to https://docs.embedchain.ai/deployment/streamlit_io
        [/bold yellow]
                      \n\n"""
        )
        subprocess.run(streamlit_deploy_cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except FileNotFoundError:
        console.print(
            """❌ [bold red]'streamlit' command not found.\n
            Please ensure Streamlit CLI is installed and in your PATH.[/bold red]"""
        )


def deploy_render():
    render_deploy_cmd = ["render", "blueprint", "launch"]

    try:
        console.print(f"🚀 [bold cyan]Running: {' '.join(render_deploy_cmd)}[/bold cyan]")
        subprocess.run(render_deploy_cmd, check=True)
        console.print("✅ [bold green]'render blueprint launch' executed successfully.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except FileNotFoundError:
        console.print(
            "❌ [bold red]'render' command not found. Please ensure Render CLI is installed and in your PATH.[/bold red]"  # noqa:E501
        )


def deploy_gradio_app():
    gradio_deploy_cmd = ["gradio", "deploy"]

    try:
        console.print(f"🚀 [bold cyan]Running: {' '.join(gradio_deploy_cmd)}[/bold cyan]")
        subprocess.run(gradio_deploy_cmd, check=True)
        console.print("✅ [bold green]'gradio deploy' executed successfully.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
    except FileNotFoundError:
        console.print(
            "❌ [bold red]'gradio' command not found. Please ensure Gradio CLI is installed and in your PATH.[/bold red]"  # noqa:E501
        )


def deploy_hf_spaces(ec_app_name):
    if not ec_app_name:
        console.print("❌ [bold red]'name' not found in embedchain.json[/bold red]")
        return
    hf_spaces_deploy_cmd = ["huggingface-cli", "upload", ec_app_name, ".", ".", "--repo-type=space"]

    try:
        console.print(f"🚀 [bold cyan]Running: {' '.join(hf_spaces_deploy_cmd)}[/bold cyan]")
        subprocess.run(hf_spaces_deploy_cmd, check=True)
        console.print("✅ [bold green]'huggingface-cli upload' executed successfully.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"❌ [bold red]An error occurred: {e}[/bold red]")
