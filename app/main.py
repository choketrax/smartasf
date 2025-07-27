from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, Depends, HTTPException

from fastapi.security.api_key import APIKeyHeader

from .docker_utils import start_container, stop_container
from .models import Registry, RegistryEntry
from .proxy_middleware import ProxyMiddleware

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Parse API keys from environment: "key1:tenant1,key2:tenant2"
raw_keys = os.getenv("API_KEYS", "test123:demo")
API_KEYS: Dict[str, str] = dict(item.split(":") for item in raw_keys.split(","))

app = FastAPI()
registry = Registry()
app.add_middleware(ProxyMiddleware, registry=registry)

RATE_LIMIT = 10  # launches per hour
launch_log: Dict[str, list[datetime]] = {}


async def get_tenant_id(api_key: str | None = Depends(API_KEY_HEADER)) -> str:
    if not api_key or api_key not in API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return API_KEYS[api_key]


def detect_runtime(repo_path: Path) -> str:
    if (repo_path / "package.json").exists():
        return "node"
    return "python"


def clone_repo(repo_url: str) -> Path:
    repo_dir = Path(tempfile.mkdtemp(prefix="repo_"))
    try:
        subprocess.run(["git", "clone", repo_url, str(repo_dir)], check=True)
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(repo_dir)
        raise HTTPException(status_code=400, detail=f"git clone failed: {exc}")
    return repo_dir


@app.post("/expose")
async def expose_repo(payload: dict, tenant_id: str = Depends(get_tenant_id)):
    repo_url = payload.get("repo_url")
    port = int(payload.get("port", 9001))
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url required")

    # rate limiting
    now = datetime.utcnow()
    log = launch_log.setdefault(tenant_id, [])
    log[:] = [t for t in log if now - t < timedelta(hours=1)]
    if len(log) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    log.append(now)

    repo_dir = clone_repo(repo_url)
    repo_name = Path(repo_url).stem
    runtime = detect_runtime(repo_dir)

    container_id, host_port = start_container(repo_dir, port, runtime)
    entry = RegistryEntry(
        tenant_id=tenant_id,
        repo_name=repo_name,
        container_id=container_id,
        host_port=host_port,
    )
    registry.add(entry)

    proxy_url = f"http://localhost:8000/tenant/{tenant_id}/{repo_name}"
    return {"message": "Repo deployed successfully", "proxy_url": proxy_url}


@app.get("/registry")
async def get_registry(tenant_id: str = Depends(get_tenant_id)):
    entries = [
        {
            "tenant_id": e.tenant_id,
            "repo_name": e.repo_name,
            "port": e.host_port,
            "created_at": e.created_at,
            "last_active": e.last_active,
        }
        for e in registry.list()
        if e.tenant_id == tenant_id
    ]
    return entries


@app.on_event("startup")
async def startup_event() -> None:
    async def cleanup_task() -> None:
        while True:
            now = datetime.utcnow()
            for entry in list(registry.list()):
                if now - entry.last_active > timedelta(minutes=30):
                    stop_container(entry.container_id)
                    registry.remove(entry.tenant_id, entry.repo_name)
            await asyncio.sleep(60)

    import asyncio

    asyncio.create_task(cleanup_task())
