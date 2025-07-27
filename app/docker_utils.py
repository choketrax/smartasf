"""Utility functions for managing Docker containers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import docker

client = docker.from_env()

PYTHON_IMAGE = os.getenv("PYTHON_RUNTIME", "python:3.11-slim")
NODE_IMAGE = os.getenv("NODE_RUNTIME", "node:18-slim")


def start_container(repo_path: Path, internal_port: int, runtime: str) -> Tuple[str, int]:
    """Start a container for the given repo and return (id, host_port)."""
    if runtime == "python":
        image = PYTHON_IMAGE
        command = (
            "bash -c 'pip install -r requirements.txt >/tmp/pip.log 2>&1 && "
            f"uvicorn main:app --host 0.0.0.0 --port {internal_port}'"
        )
    else:
        image = NODE_IMAGE
        command = (
            "bash -c 'npm install >/tmp/npm.log 2>&1 && "
            f"node index.js'"
        )
    ports = {f"{internal_port}/tcp": None}
    container = client.containers.run(
        image,
        command=command,
        working_dir="/app",
        volumes={str(repo_path): {"bind": "/app", "mode": "rw"}},
        detach=True,
        network_mode="bridge",
        mem_limit="512m",
        cpu_period=100000,
        cpu_quota=50000,
        ports=ports,
    )
    container.reload()
    host_port_str = container.attrs["NetworkSettings"]["Ports"][f"{internal_port}/tcp"][0]["HostPort"]
    return container.id, int(host_port_str)


def stop_container(container_id: str) -> None:
    """Stop and remove a container by id."""
    try:
        container = client.containers.get(container_id)
        container.stop(timeout=5)
        container.remove(force=True)
    except docker.errors.NotFound:
        pass
