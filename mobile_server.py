from __future__ import annotations

import argparse
import ipaddress
import hmac
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from rooster_engine.autonomous import AutonomousCoder
from rooster_engine.core import AutonomousEngineer

app = FastAPI(title="Rooster Mobile Companion API", version="1.2")
engine = AutonomousEngineer(os.getcwd(), os.path.expanduser("~/.rooster_mobile_tasks.json"))
TOKEN = os.getenv("ROOSTER_API_TOKEN", "")
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rooster-mobile")
_tasks: dict[str, dict[str, Any]] = {}
_tasks_lock = threading.Lock()


class TaskRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=2000)


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


def require_token(authorization: str | None = Header(default=None)) -> None:
    if not TOKEN:
        raise HTTPException(status_code=503, detail="Set ROOSTER_API_TOKEN on the Rooster computer first.")
    expected = f"Bearer {TOKEN}"
    if not hmac.compare_digest(authorization or "", expected):
        raise HTTPException(status_code=401, detail="Invalid Rooster API token.")


def _run_task(task_id: str, objective: str) -> None:
    with _tasks_lock:
        _tasks[task_id]["status"] = "running"
    try:
        result = AutonomousCoder(engine).run(objective, task_id=task_id)
        with _tasks_lock:
            _tasks[task_id].update(
                status=result.status,
                iterations=result.iterations,
                summary=result.summary,
                evidence=result.evidence,
            )
    except Exception as exc:
        with _tasks_lock:
            _tasks[task_id].update(
                status="stopped" if engine.guard.emergency_stop.stopped else "failed",
                summary=str(exc)[:1000],
            )


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "name": "Rooster Autonomous Engineer", "version": "2"}


@app.get("/status", dependencies=[Depends(require_token)])
def status() -> dict[str, object]:
    with _tasks_lock:
        active = next(
            ({"task_id": task_id, "objective": task["objective"], "status": task["status"]}
             for task_id, task in reversed(list(_tasks.items()))
             if task["status"] in {"queued", "running"}),
            None,
        )
    return {
        "ok": True,
        "emergency_stop": engine.guard.emergency_stop.stopped,
        "tools": engine.tools.names(),
        "active_task": active,
        "chat_ready": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.post("/chat", dependencies=[Depends(require_token)])
def chat(request: ChatRequest) -> dict[str, object]:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="Set OPENAI_API_KEY on the Rooster PC first.")
    try:
        from openai import OpenAI
        client = OpenAI()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Rooster, the user's practical AI assistant and companion for Rooster Autonomous Engineer. "
                    "Be conversational, helpful, concise, and honest. You can discuss plans and help the user prepare tasks, "
                    "but ordinary chat does not execute commands or modify files. If the user wants engineering work performed, "
                    "explain that they should use the Run Task control. Never claim a task was run unless task status confirms it. "
                    "Respect safety boundaries and ask before destructive or consequential actions."
                ),
            },
            *[{"role": item.role, "content": item.content} for item in request.messages[-20:]],
        ]
        response = client.chat.completions.create(
            model=os.getenv("ROOSTER_CHAT_MODEL", "gpt-4o-mini"),
            messages=messages,
            max_tokens=700,
            timeout=30.0,
        )
        answer = response.choices[0].message.content or "I didn't get a reply. Please try again."
        return {"ok": True, "reply": answer}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat request failed: {str(exc)[:300]}") from exc


@app.post("/tasks", dependencies=[Depends(require_token)])
def start_task(request: TaskRequest) -> dict[str, object]:
    objective = request.objective.strip()
    if not objective:
        raise HTTPException(status_code=422, detail="Objective cannot be blank.")
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="Set OPENAI_API_KEY on the Rooster PC before starting autonomous tasks.")
    if engine.guard.emergency_stop.stopped:
        raise HTTPException(status_code=409, detail="Emergency stop is active. Reset it before starting a task.")

    with _tasks_lock:
        if any(task["status"] in {"queued", "running"} for task in _tasks.values()):
            raise HTTPException(status_code=409, detail="A task is already running. Refresh its status before starting another.")
        task_id = uuid.uuid4().hex
        _tasks[task_id] = {
            "task_id": task_id,
            "objective": objective,
            "status": "queued",
            "iterations": 0,
            "summary": "Task queued.",
            "evidence": [],
        }
    _executor.submit(_run_task, task_id, objective)
    engine.guard.audit.write("mobile_task_queued", task_id=task_id, objective=objective)
    return {"ok": True, "task_id": task_id, "status": "queued"}


@app.get("/tasks/{task_id}", dependencies=[Depends(require_token)])
def get_task(task_id: str) -> dict[str, object]:
    with _tasks_lock:
        task = _tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found on this server session.")
        return dict(task)


@app.post("/stop", dependencies=[Depends(require_token)])
def stop() -> dict[str, object]:
    engine.emergency_stop()
    with _tasks_lock:
        for task in _tasks.values():
            if task["status"] in {"queued", "running"}:
                task["status"] = "stopped"
                task["summary"] = "Emergency stop requested."
    return {"ok": True, "emergency_stop": True}


@app.post("/reset", dependencies=[Depends(require_token)])
def reset() -> dict[str, object]:
    engine.reset_emergency_stop()
    return {"ok": True, "emergency_stop": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Rooster mobile companion API")
    parser.add_argument("--host", default="127.0.0.1", help="Use 127.0.0.1 for local-only access.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ssl-certfile", help="TLS certificate file required for LAN access.")
    parser.add_argument("--ssl-keyfile", help="TLS private key file required for LAN access.")
    args = parser.parse_args()

    try:
        is_loopback = args.host.lower() == "localhost" or ipaddress.ip_address(args.host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback and not (args.ssl_certfile and args.ssl_keyfile):
        parser.error("Non-loopback access requires --ssl-certfile and --ssl-keyfile; do not expose the API over plain HTTP.")
    if bool(args.ssl_certfile) != bool(args.ssl_keyfile):
        parser.error("Provide both --ssl-certfile and --ssl-keyfile.")

    import uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        ssl_certfile=args.ssl_certfile,
        ssl_keyfile=args.ssl_keyfile,
    )


if __name__ == "__main__":
    main()
