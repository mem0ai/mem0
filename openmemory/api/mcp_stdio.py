import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from mcp.types import JSONRPCMessage

api_dir = Path(__file__).resolve().parent
openmemory_dir = api_dir.parent
ui_dir = openmemory_dir / "ui"
runtime_dir = api_dir / ".openmemory-runtime"
os.chdir(api_dir)


def env_flag(name, default=True):
    value = os.getenv(name)

    if value is None:
        return default

    return value.lower() not in {"0", "false", "no", "off"}


def local_port_is_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def wait_for_port(host, port, timeout=30):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if local_port_is_open(host, port):
            return True
        time.sleep(0.25)

    return False


def acquire_autostart_lock(name, host, port, timeout=60, stale_after=60):
    runtime_dir.mkdir(parents=True, exist_ok=True)
    lock_path = runtime_dir / f"{name}.lock"
    deadline = time.monotonic() + timeout

    while True:
        if local_port_is_open(host, port):
            return "port-open"

        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                lock_age = time.time() - lock_path.stat().st_mtime
            except FileNotFoundError:
                continue

            if lock_age > stale_after:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                continue

            if time.monotonic() >= deadline:
                return None

            time.sleep(0.25)
            continue

        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        return fd, lock_path


def release_autostart_lock(lock):
    if lock is None:
        return

    fd, lock_path = lock
    os.close(fd)

    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def open_runtime_log(name):
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(runtime_dir / f"{name}.log", "ab", buffering=0)
    log_file.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode("utf-8"))
    return log_file


def subprocess_creation_flags():
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW

    return 0


def start_background_process(name, command, cwd, env):
    log_file = open_runtime_log(name)

    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=subprocess_creation_flags(),
        )
    except Exception as exc:
        log_file.write(f"Failed to start {name}: {exc}\n".encode("utf-8", errors="replace"))
        log_file.close()
        return None

    log_file.close()
    return process


def ensure_openmemory_api(host, port):
    if local_port_is_open(host, port) or not env_flag("OPENMEMORY_AUTOSTART_API"):
        return

    lock = acquire_autostart_lock("api", host, port)

    if lock is None or lock == "port-open":
        return

    if local_port_is_open(host, port):
        release_autostart_lock(lock)
        return

    try:
        env = os.environ.copy()
        env.setdefault("PYTHONWARNINGS", "ignore")
        env["OPENMEMORY_API_HOST"] = host
        env["OPENMEMORY_API_PORT"] = str(port)

        process = start_background_process(
            "api",
            [sys.executable, str(api_dir / "run_openmemory.py")],
            api_dir,
            env,
        )

        if process is not None:
            wait_for_port(host, port)
    finally:
        release_autostart_lock(lock)


def find_next_command():
    node = shutil.which("node")
    next_bin = ui_dir / "node_modules" / "next" / "dist" / "bin" / "next"

    if node and next_bin.exists():
        return [node, str(next_bin)]

    pnpm = shutil.which("pnpm.cmd") or shutil.which("pnpm")

    if pnpm:
        return [pnpm, "run", "dev", "--"]

    return None


def ensure_openmemory_ui(host, port, api_url, user_id):
    if local_port_is_open(host, port) or not env_flag("OPENMEMORY_AUTOSTART_UI"):
        return

    lock = acquire_autostart_lock("ui", host, port)

    if lock is None or lock == "port-open":
        return

    if local_port_is_open(host, port):
        release_autostart_lock(lock)
        return

    try:
        command = find_next_command()

        if command is None:
            log_file = open_runtime_log("ui")
            log_file.write(b"Failed to start UI: neither node/next nor pnpm was found.\n")
            log_file.close()
            return

        env = os.environ.copy()
        env["NEXT_PUBLIC_API_URL"] = api_url
        env["NEXT_PUBLIC_USER_ID"] = user_id

        process = start_background_process(
            "ui",
            [*command, "dev", "-H", host, "-p", str(port)]
            if len(command) == 2
            else [*command, "-H", host, "-p", str(port)],
            ui_dir,
            env,
        )

        if process is not None:
            wait_for_port(host, port)
    finally:
        release_autostart_lock(lock)


def ensure_local_openmemory(user_id):
    api_host = os.getenv("OPENMEMORY_API_HOST", "127.0.0.1")
    api_port = int(os.getenv("OPENMEMORY_API_PORT", "8765"))
    ui_host = os.getenv("OPENMEMORY_UI_HOST", "127.0.0.1")
    ui_port = int(os.getenv("OPENMEMORY_UI_PORT", "3000"))
    api_url = os.getenv("NEXT_PUBLIC_API_URL", f"http://{api_host}:{api_port}")

    ensure_openmemory_api(api_host, api_port)
    ensure_openmemory_ui(ui_host, ui_port, api_url, user_id)


def default_user_id():
    return os.getenv("USER") or os.getenv("USERNAME") or "default"


def ignore_invalid_stdin_lines():
    source = sys.stdin.buffer
    output = sys.stdout.buffer
    read_fd, write_fd = os.pipe()
    output_lock = threading.Lock()

    def write_jsonrpc_error(code, message, data=None, id_=None):
        response = {
            "jsonrpc": "2.0",
            "id": id_,
            "error": {
                "code": code,
                "message": message,
            },
        }

        if data is not None:
            response["error"]["data"] = data

        encoded = (json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

        with output_lock:
            output.write(encoded)
            output.flush()

    def extract_jsonrpc_id(value):
        if not isinstance(value, dict):
            return None

        id_ = value.get("id")

        if id_ is None or isinstance(id_, (str, int, float)):
            return id_

        return None

    def copy_valid_lines():
        with os.fdopen(write_fd, "wb") as writer:
            for line in source:
                if not line.strip():
                    continue

                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    write_jsonrpc_error(
                        -32700,
                        "Parse error",
                        data=f"Invalid JSON received on stdin: {exc.msg} at line {exc.lineno} column {exc.colno}",
                        id_=None,
                    )
                    continue

                try:
                    JSONRPCMessage.model_validate(value)
                except Exception as exc:
                    write_jsonrpc_error(
                        -32600,
                        "Invalid Request",
                        data=f"Invalid JSON-RPC message received on stdin: {exc}",
                        id_=extract_jsonrpc_id(value),
                    )
                    continue

                writer.write(line)
                writer.flush()

    threading.Thread(target=copy_valid_lines, daemon=True).start()
    sys.stdin = os.fdopen(read_fd, "r", encoding="utf-8", errors="replace")


def main():
    user_id = os.getenv("OPENMEMORY_USER_ID", default_user_id())
    client_name = os.getenv("OPENMEMORY_CLIENT_NAME", "codex")
    ensure_local_openmemory(user_id)

    from app.database import Base, engine
    from app.mcp_server import client_name_var, mcp, user_id_var

    Base.metadata.create_all(bind=engine)
    user_id_var.set(user_id)
    client_name_var.set(client_name)
    mcp._mcp_server.name = "mem0-mcp-server"
    ignore_invalid_stdin_lines()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
