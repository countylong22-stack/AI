from __future__ import annotations

import argparse
import os

from fastapi import Depends, FastAPI, Header, HTTPException

from rooster_engine.core import AutonomousEngineer

app = FastAPI(title="Rooster Mobile Companion API", version="1.0")
engine = AutonomousEngineer(os.getcwd(), os.path.expanduser("~/.rooster_mobile_tasks.json"))
TOKEN = os.getenv("ROOSTER_API_TOKEN", "")


def require_token(authorization: str | None = Header(default=None)) -> None:
    if not TOKEN:
        raise HTTPException(status_code=503, detail="Set ROOSTER_API_TOKEN on the Rooster computer first.")
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid Rooster API token.")


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "name": "Rooster Autonomous Engineer", "version": "2"}


@app.get("/status", dependencies=[Depends(require_token)])
def status() -> dict[str, object]:
    return {
        "ok": True,
        "emergency_stop": engine.guard.emergency_stop.stopped,
        "tools": engine.tools.names(),
    }


@app.post("/stop", dependencies=[Depends(require_token)])
def stop() -> dict[str, object]:
    engine.emergency_stop()
    return {"ok": True, "emergency_stop": True}


@app.post("/reset", dependencies=[Depends(require_token)])
def reset() -> dict[str, object]:
    engine.reset_emergency_stop()
    return {"ok": True, "emergency_stop": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Rooster mobile companion API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
