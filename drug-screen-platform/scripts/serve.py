"""
Start the web API on 127.0.0.1:8000 (loopback only, never the LAN).

    uv run python scripts/serve.py            # add --reload while developing
"""

import sys

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.app:app", host="127.0.0.1", port=8000, reload="--reload" in sys.argv)
