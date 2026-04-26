import subprocess
import sys
from pathlib import Path

# Отвечает за запуск streamlit приложения на сервере
class PreviewRuntimeService:
    def __init__(self):
        self.process = None
        self.port = 8501
        self.preview_app_path = Path("preview_app.py")

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        if self.is_running():
            return

        if not self.preview_app_path.exists():
            raise FileNotFoundError("preview_app.py not found")

        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(self.preview_app_path),
                "--server.port",
                str(self.port),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        if self.is_running():
            self.process.terminate()
            self.process.wait(timeout=5)


preview_runtime_service = PreviewRuntimeService()