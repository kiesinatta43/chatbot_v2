from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the local index and run the chatbot server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--backend", choices=["extractive", "ollama"], default="extractive")
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--skip-ingest", action="store_true")
    return parser.parse_args()


def resolve_server_port(host: str, requested_port: int) -> int:
    if can_bind(host, requested_port):
        return requested_port

    fallback_port = find_free_port(host)
    print(
        f"Port {requested_port} on {host} is unavailable. "
        f"Starting the server on port {fallback_port} instead."
    )
    return fallback_port


def can_bind(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
    except OSError:
        return False
    return True


def find_free_port(host: str) -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])
    except OSError as exc:
        raise RuntimeError(
            f"Unable to bind a local server on host {host}. "
            "Check whether the host is valid and whether local socket binding is permitted."
        ) from exc


def main() -> None:
    args = parse_args()
    env = os.environ.copy()
    env["CHAT_BACKEND"] = args.backend
    env["OLLAMA_MODEL"] = args.model
    server_port = resolve_server_port(args.host, args.port)

    if not args.skip_ingest:
        subprocess.run([sys.executable, "-m", "app.ingest"], cwd=ROOT, env=env, check=True)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            args.host,
            "--port",
            str(server_port),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
