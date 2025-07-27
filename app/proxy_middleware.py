"""ASGI middleware to proxy tenant requests to running containers."""
from __future__ import annotations

import aiohttp
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .models import Registry


class ProxyMiddleware:
    def __init__(self, app: ASGIApp, registry: Registry):
        self.app = app
        self.registry = registry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/tenant/"):
            parts = scope["path"].split("/")
            if len(parts) >= 4:
                tenant_id = parts[2]
                repo_name = parts[3]
                new_path = "/" + "/".join(parts[4:])
                entry = self.registry.get(tenant_id, repo_name)
                if entry:
                    self.registry.update_last_active(tenant_id, repo_name)
                    url = f"http://127.0.0.1:{entry.host_port}{new_path}"
                    if scope.get("query_string"):
                        url += "?" + scope["query_string"].decode()
                    request = Request(scope, receive)
                    body = await request.body()
                    async with aiohttp.ClientSession() as session:
                        async with session.request(
                            request.method,
                            url,
                            headers={k.decode(): v.decode() for k, v in scope["headers"]},
                            data=body,
                            allow_redirects=False,
                        ) as resp:
                            response_headers = [(k, v) for k, v in resp.headers.items()]
                            streaming = StreamingResponse(
                                resp.content.iter_chunked(1024),
                                status_code=resp.status,
                                headers=dict(response_headers),
                            )
                            await streaming(scope, receive, send)
                            return
        await self.app(scope, receive, send)
