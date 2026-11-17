import asyncio
import pytest
from app.middleware.security_headers import SecurityHeaders


@pytest.mark.parametrize('path,status', [('/health',200),('/auth/login',401),('/auth/google/callback',303),('/sharing/example/images/1',200),('/missing',404)])
def test_headers_preserve_response_and_redirect(path,status):
    messages=[]
    async def downstream(scope,receive,send):
        await send({'type':'http.response.start','status':status,'headers':[(b'location',b'https://accounts.google.com/'),(b'access-control-allow-origin',b'https://frontend.example')]})
        await send({'type':'http.response.body','body':b'unchanged'})
    async def send(message): messages.append(message)
    asyncio.run(SecurityHeaders(downstream)({'type':'http','path':path},None,send))
    headers=dict(messages[0]['headers'])
    assert messages[0]['status']==status and messages[1]['body']==b'unchanged'
    assert headers[b'x-frame-options']==b'DENY'
    assert b"frame-ancestors 'none'" in headers[b'content-security-policy']
    assert headers[b'location']==b'https://accounts.google.com/'
    assert headers[b'access-control-allow-origin']==b'https://frontend.example'
    assert headers[b'referrer-policy']==b'no-referrer'
    assert b'strict-transport-security' not in headers
    if path.startswith('/auth/'):
        assert headers[b'cache-control']==b'no-store'


def test_non_http_passes_through():
    scopes=[]
    async def downstream(scope,receive,send): scopes.append(scope)
    scope={'type':'websocket'}
    asyncio.run(SecurityHeaders(downstream)(scope,None,None))
    assert scopes==[scope]
