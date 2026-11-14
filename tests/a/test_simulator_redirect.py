import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tools.sim.run import Actor, Step, _play


def test_simulator_never_follows_redirects_or_forwards_labels():
    hits = []

    class Destination(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(dict(self.headers))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Destination)

    class Redirect(Destination):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/collect")
            self.end_headers()

    source = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in (source, target)
    ]
    for thread in threads:
        thread.start()
    try:
        actor = Actor("fixture", "192.0.2.1", "test-agent", "human", steps=[Step(0, "GET", "/")])
        results = []
        _play(
            f"http://127.0.0.1:{source.server_port}",
            actor,
            "test",
            "private-secret",
            time.monotonic(),
            results,
        )
        assert hits == []
        assert results[0][-1] == 302
    finally:
        for server in (source, target):
            server.shutdown()
            server.server_close()
