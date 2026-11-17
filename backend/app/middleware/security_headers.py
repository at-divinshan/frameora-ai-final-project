"""Compatible baseline headers; TLS/HSTS and frontend hosting remain deployment concerns."""
from starlette.datastructures import MutableHeaders


class SecurityHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def protected_send(message):
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                # No script/connect/image restrictions: preserve docs, OAuth,
                # hosted Checkout redirects, previews and development tooling.
                headers['Content-Security-Policy'] = "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
                headers['X-Frame-Options'] = 'DENY'
                headers['X-Content-Type-Options'] = 'nosniff'
                headers['Referrer-Policy'] = 'no-referrer'
                if scope.get('path', '').startswith('/auth/'):
                    headers['Cache-Control'] = 'no-store'
                    headers['Pragma'] = 'no-cache'
            await send(message)

        await self.app(scope, receive, protected_send)
