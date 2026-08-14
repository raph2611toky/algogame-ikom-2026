import os
import sys
import socket
import time
import subprocess
from pathlib import Path

import requests
import uvicorn


def find_free_port() -> int:
    for port in range(18000, 18100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue

    raise RuntimeError("Aucun port local disponible.")


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")

    if not base:
        base = str(Path.home())

    path = Path(base) / "Kakafandodo"
    path.mkdir(parents=True, exist_ok=True)

    return path


def resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS)
    else:
        root = Path(__file__).resolve().parent.parent

    return root / relative


def run_backend(port: int) -> None:
    data_dir = app_data_dir()

    os.environ["KAKAFANDODO_DATA_DIR"] = str(data_dir)

    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )


def wait_backend(port: int, timeout: float = 20.0) -> bool:
    url = f"http://127.0.0.1:{port}/api/v1/health"

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=0.5)

            if response.ok:
                return True
        except requests.RequestException:
            pass

        time.sleep(0.15)

    return False


def run_launcher() -> int:
    port = find_free_port()

    flags = 0

    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW

    backend = subprocess.Popen(
        [
            sys.executable,
            "--backend-worker",
            f"--port={port}",
        ],
        creationflags=flags,
    )

    try:
        if not wait_backend(port):
            backend.terminate()
            return 20

        godot_exe = resource_path(
            "godot/Kakafandodo2D.exe"
        )

        game = subprocess.Popen(
            [
                str(godot_exe),
                "--",
                f"--backend-host=127.0.0.1",
                f"--backend-port={port}",
                "--packaged",
            ]
        )

        return game.wait()

    finally:
        if backend.poll() is None:
            backend.terminate()

            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()


def argument_value(prefix: str, default: str) -> str:
    for argument in sys.argv:
        if argument.startswith(prefix):
            return argument.split("=", 1)[1]

    return default


if __name__ == "__main__":
    if "--backend-worker" in sys.argv:
        port = int(
            argument_value("--port=", "18000")
        )

        run_backend(port)
    else:
        raise SystemExit(run_launcher())