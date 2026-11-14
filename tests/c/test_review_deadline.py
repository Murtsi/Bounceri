import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from bouncer.review import HttpTransport


def test_request_deadline_includes_the_entire_slow_response():
    calls = []

    class SlowResponse(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(1)
            body = b'{"valid":true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                for byte in body:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.02)  # Each read is fast; the total response exceeds the deadline.
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowResponse)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(TimeoutError):
            HttpTransport().get_json(f"http://127.0.0.1:{server.server_port}", {}, 0.06)
        assert calls == [1]
    finally:
        server.shutdown()
        server.server_close()
