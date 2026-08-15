from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")

    if not base:
        base = str(Path.home())

    path = Path(base) / "Kakafandodo"
    path.mkdir(parents=True, exist_ok=True)

    return path


def setup_stdio():
    """
    PyInstaller --windowed met sys.stdout/sys.stderr à None sous Windows.
    On redirige donc vers un fichier de log.
    """
    log_dir = app_data_dir()

    log_name = (
        "backend.log"
        if "--backend-worker" in sys.argv
        else "launcher.log"
    )

    log_path = log_dir / log_name

    log_file = open(
        log_path,
        "a",
        encoding="utf-8",
        buffering=1,
    )

    if sys.stdout is None:
        sys.stdout = log_file

    if sys.stderr is None:
        sys.stderr = log_file

    return log_file


_LOG_FILE = setup_stdio()


import ctypes
import socket
import subprocess
import time

import requests
import uvicorn


DEFAULT_HOST = "127.0.0.1"
PORT_START = 18000
PORT_END = 18100


def resource_path(relative: str) -> Path:
    """
    En développement :
        racine_projet/<relative>

    Avec PyInstaller onefile :
        _MEIPASS/<relative>
    """
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS)
    else:
        root = Path(__file__).resolve().parent.parent

    return root / relative


def find_free_port() -> int:
    for port in range(PORT_START, PORT_END):
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as sock:
            try:
                sock.bind((DEFAULT_HOST, port))
                return port
            except OSError:
                continue

    raise RuntimeError(
        "Aucun port local disponible entre "
        f"{PORT_START} et {PORT_END - 1}."
    )


def configure_backend_storage(port: int) -> None:
    """
    IMPORTANT :
    backend/app/core/config.py lit ces variables
    au moment de l'import de app.main.
    Elles doivent donc être définies AVANT :
        from app.main import app
    """
    data_dir = app_data_dir()

    output_dir = data_dir / "output"
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    os.environ["KAKAFANDODO_HOST"] = DEFAULT_HOST
    os.environ["KAKAFANDODO_PORT"] = str(port)

    os.environ["KAKAFANDODO_SETTINGS_FILE"] = str(
        data_dir / "settings.json"
    )

    os.environ["KAKAFANDODO_OUTPUT_DIR"] = str(
        output_dir
    )


def run_backend(port: int) -> None:
    configure_backend_storage(port)

    # Import volontairement APRÈS les variables
    # d'environnement.
    from app.main import app

    uvicorn.run(
        app,
        host=DEFAULT_HOST,
        port=port,
        log_level="warning",
        access_log=False,
    )


def wait_backend(
    port: int,
    timeout: float = 30.0,
) -> bool:
    url = (
        f"http://{DEFAULT_HOST}:{port}"
        "/api/v1/health"
    )

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            response = requests.get(
                url,
                timeout=0.75,
            )

            if response.ok:
                return True

        except requests.RequestException:
            pass

        time.sleep(0.20)

    return False


def argument_value(
    prefix: str,
    default: str,
) -> str:
    for argument in sys.argv:
        if argument.startswith(prefix):
            return argument.split("=", 1)[1]

    return default


def show_error(message: str) -> None:
    """
    Message visible même avec PyInstaller console=False.
    """
    try:
        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            "Kakafandodo",
            0x10,
        )
    except Exception:
        print(message)


def sanitized_external_environment() -> dict[str, str]:
    """
    Godot est un programme externe au runtime Python.

    PyInstaller modifie la recherche DLL sous Windows.
    On la remet dans son état normal avant de lancer Godot.
    """
    env = os.environ.copy()

    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetDllDirectoryW(
                None
            )
        except Exception as exc:
            print(
                "[Launcher] SetDllDirectoryW:",
                exc,
            )

    bundle_dir = getattr(
        sys,
        "_MEIPASS",
        None,
    )

    if bundle_dir:
        bundle_path = os.path.normcase(
            os.path.abspath(bundle_dir)
        )

        cleaned_path: list[str] = []

        for item in env.get(
            "PATH",
            "",
        ).split(os.pathsep):

            if not item:
                continue

            normalized = os.path.normcase(
                os.path.abspath(item)
            )

            if normalized.startswith(
                bundle_path
            ):
                continue

            cleaned_path.append(item)

        env["PATH"] = os.pathsep.join(
            cleaned_path
        )

    return env


def stop_backend(
    backend: subprocess.Popen,
) -> None:
    if backend.poll() is not None:
        return

    backend.terminate()

    try:
        backend.wait(timeout=5)

    except subprocess.TimeoutExpired:
        backend.kill()

        try:
            backend.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def run_launcher() -> int:
    print(
        "[Launcher] Kakafandodo starting..."
    )

    port = find_free_port()

    print(
        "[Launcher] Backend:",
        f"{DEFAULT_HOST}:{port}",
    )

    creation_flags = 0

    if os.name == "nt":
        creation_flags = (
            subprocess.CREATE_NO_WINDOW
        )

    backend = subprocess.Popen(
        [
            sys.executable,
            "--backend-worker",
            f"--port={port}",
        ],
        creationflags=creation_flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        if not wait_backend(
            port,
            timeout=30.0,
        ):
            show_error(
                "Le backend Kakafandodo n'a pas "
                "démarré correctement.\n\n"
                "Consulte le fichier :\n"
                f"{app_data_dir() / 'backend.log'}"
            )

            return 20

        print(
            "[Launcher] Backend ready."
        )

        godot_exe = resource_path(
            "godot/kakafandodo2d.exe"
        )

        godot_pck = resource_path(
            "godot/kakafandodo2d.pck"
        )

        if not godot_exe.exists():
            show_error(
                "Exécutable Godot introuvable :\n"
                f"{godot_exe}"
            )

            return 21

        if not godot_pck.exists():
            show_error(
                "Pack Godot introuvable :\n"
                f"{godot_pck}"
            )

            return 22

        print(
            "[Launcher] Godot:",
            godot_exe,
        )

        game_environment = (
            sanitized_external_environment()
        )

        game = subprocess.Popen(
            [
                str(godot_exe),
                "--",
                f"--backend-host={DEFAULT_HOST}",
                f"--backend-port={port}",
                "--packaged",
            ],
            cwd=str(godot_exe.parent),
            env=game_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        exit_code = game.wait()

        print(
            "[Launcher] Godot exit:",
            exit_code,
        )

        return exit_code

    except Exception as exc:
        print(
            "[Launcher] Fatal error:",
            repr(exc),
        )

        show_error(
            "Erreur lors du lancement de "
            "Kakafandodo.\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            "Consulte :\n"
            f"{app_data_dir() / 'launcher.log'}"
        )

        return 99

    finally:
        stop_backend(backend)

        print(
            "[Launcher] Backend stopped."
        )


if __name__ == "__main__":
    if "--backend-worker" in sys.argv:
        worker_port = int(
            argument_value(
                "--port=",
                "18000",
            )
        )

        run_backend(worker_port)

    else:
        raise SystemExit(
            run_launcher()
        )