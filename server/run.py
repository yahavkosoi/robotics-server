import json
from pathlib import Path

from uvicorn import run


def _read_backend_port() -> int:
    settings_path = Path(__file__).resolve().parent.parent / "data" / "settings.json"
    default_port = 8080
    if not settings_path.exists():
        return default_port

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_port

    port = payload.get("backend_port", default_port)
    if not isinstance(port, int) or not (1 <= port <= 65535):
        return default_port
    return port

if __name__ == "__main__":
    run("server.app:app", host="0.0.0.0", port=_read_backend_port(), reload=True)
