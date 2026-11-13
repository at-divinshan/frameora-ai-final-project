"""Bound AI multipart requests before Starlette spools uploaded files to disk."""

from starlette.responses import JSONResponse
import re


class AIUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not re.fullmatch(r"/(?:ai/generations|owner/ai/generations|owner/projects/[0-9]+/ai/generations)/?", scope.get("path", "")) or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        limit = 11 * 1024 * 1024  # Two 5 MiB files plus bounded form overhead.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
                response = JSONResponse({"detail": "Upload request is too large."}, status_code=413,
                                        headers={"Cache-Control": "no-store"})
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
