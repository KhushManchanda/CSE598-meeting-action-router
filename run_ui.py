"""Launch the local UI without Streamlit's credential prompt or secrets-store loading.

API configuration is read by the app only after its explicit consent control.
"""
from pathlib import Path

from streamlit.web import bootstrap


if __name__ == "__main__":
    options = {
        "server.address": "127.0.0.1",
        "server.port": 8501,
        "server.headless": True,
        "server.fileWatcherType": "none",
        "browser.gatherUsageStats": False,
        "secrets.files": [],
        "theme.base": "light",
        "theme.primaryColor": "#12695e",
        "theme.backgroundColor": "#f6f7f9",
        "theme.secondaryBackgroundColor": "#ffffff",
        "theme.textColor": "#192b3c",
    }
    bootstrap.load_config_options(options)
    bootstrap.run(str(Path(__file__).resolve().parent / "streamlit_app.py"), False, [], options)
