from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return a bundled asset path for source, zip-runtime, or PyInstaller builds."""
    bundled_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundled_root) if bundled_root else Path(__file__).resolve().parent.parent
    return root.joinpath(*parts)


def app_icon_path() -> Path:
    suffix = "app.ico" if sys.platform == "win32" else "app.png"
    return resource_path("assets", "icons", suffix)
