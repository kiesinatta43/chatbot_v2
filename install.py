from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = ROOT / "requirements.txt"
DEFAULT_MODEL = "llama3.1:8b"


def run_command(command: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> int:
    print(f"\n$ {' '.join(command)}")
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if check and completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")
    return completed.returncode


def install_python_dependencies() -> None:
    run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    run_command([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])


def detect_ollama() -> bool:
    return shutil.which("ollama") is not None


def install_ollama() -> None:
    system = platform.system().lower()
    if system == "linux":
        shell_command = "curl -fsSL https://ollama.com/install.sh | sh"
        run_command(["sh", "-c", shell_command])
        return

    if system == "darwin":
        if shutil.which("brew"):
            run_command(["brew", "install", "ollama"])
            return
        raise RuntimeError("Homebrew is required for automatic Ollama install on macOS.")

    if system == "windows":
        raise RuntimeError(
            "Automatic Ollama installation is not implemented for Windows. "
            "Install it manually from https://ollama.com/download/windows ."
        )

    raise RuntimeError(f"Unsupported operating system for automatic Ollama install: {platform.system()}")


def pull_ollama_model(model: str) -> None:
    run_command(["ollama", "pull", model])


def print_next_steps(model: str, backend: str) -> None:
    print("\nInstallation complete.\n")
    print("Next steps:")
    print("1. Add your school documents to src/")
    print(f"2. Build the search index: {sys.executable} -m app.ingest")
    if backend == "ollama":
        print(
            "3. Start the server with Ollama: "
            f"CHAT_BACKEND=ollama OLLAMA_MODEL={model} {sys.executable} -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
        )
    else:
        print(f"3. Start the server: {sys.executable} -m uvicorn app.main:app --host 0.0.0.0 --port 8000")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the local school chatbot into the current system Python and optionally configure a local Ollama model."
    )
    parser.add_argument(
        "--backend",
        choices=["extractive", "ollama"],
        default="extractive",
        help="Answer generation backend to prepare.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Ollama model to pull when using the ollama backend.",
    )
    parser.add_argument(
        "--skip-ollama-install",
        action="store_true",
        help="Do not attempt to install Ollama automatically.",
    )
    parser.add_argument(
        "--skip-model-pull",
        action="store_true",
        help="Do not pull the Ollama model automatically.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    install_python_dependencies()

    if args.backend == "ollama":
        if not detect_ollama():
            if args.skip_ollama_install:
                raise RuntimeError("Ollama is not installed. Remove --skip-ollama-install or install Ollama manually.")
            install_ollama()

        if not args.skip_model_pull:
            pull_ollama_model(args.model)

    print_next_steps(args.model, args.backend)


if __name__ == "__main__":
    main()
