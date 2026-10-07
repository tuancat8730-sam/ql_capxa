"""The worker answers 200 on $PORT so Cloud Run keeps it running."""

import asyncio

from app.worker import serve_health


async def _get(port: int, request: bytes = b"GET / HTTP/1.1\r\nHost: x\r\n\r\n") -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(request)
    await writer.drain()
    data = await reader.read()
    writer.close()
    return data


async def test_the_health_listener_answers_200() -> None:
    server = await serve_health(0)
    port = server.sockets[0].getsockname()[1]
    try:
        reply = await _get(port)
        assert reply.startswith(b"HTTP/1.1 200 OK") and reply.endswith(b"ok")
        again = await _get(port, b"GET /anything HTTP/1.1\r\n\r\n")  # any path, any number of times
        assert again.startswith(b"HTTP/1.1 200 OK")
    finally:
        server.close()
        await server.wait_closed()


async def test_a_client_that_sends_nothing_does_not_hang_the_listener() -> None:
    server = await serve_health(0)
    port = server.sockets[0].getsockname()[1]
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.close()  # connect and leave without a request
        await asyncio.sleep(0.1)
        assert (await _get(port)).startswith(b"HTTP/1.1 200 OK")
    finally:
        server.close()
        await server.wait_closed()
