import os
import subprocess
import sys
from pathlib import Path

# Отвечает за запуск streamlit приложения на сервере
class PreviewRuntimeService:
    def __init__(self):
        self.process = None
        self.project_root = Path(__file__).resolve().parents[2]
        self.port = int(os.getenv("PREVIEW_PORT", "8501"))
        self.host = os.getenv("PREVIEW_HOST", "127.0.0.1")
        self.preview_app_path = self.project_root / "preview_app.py"

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        if self.is_running():
            return

        if not self.preview_app_path.exists():
            raise FileNotFoundError("preview_app.py not found")

        environment = os.environ.copy()
        environment.setdefault(
            "STREAMLIT_BUILDER_API_BASE",
            "http://localhost:8000",
        )

        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(self.preview_app_path),
                "--server.port",
                str(self.port),
                "--server.address",
                self.host,
                "--server.headless",
                "true",
                "--server.fileWatcherType",
                "none",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=str(self.project_root),
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

    def stop(self) -> None:
        if self.is_running():
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            finally:
                self.process = None


preview_runtime_service = PreviewRuntimeService()
