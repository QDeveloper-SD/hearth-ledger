from __future__ import annotations

import os

import uvicorn

from backend.app import create_app

if __name__ == "__main__":
    host = os.environ.get("HEARTH_HOST", "127.0.0.1")
    port = int(os.environ.get("HEARTH_PORT", "8765"))
    uvicorn.run(create_app(), host=host, port=port)
