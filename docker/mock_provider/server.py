import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NAME = os.getenv("PROVIDER_NAME", "primary")
state = {"mode": os.getenv("MODE", "ok"), "delay": float(os.getenv("DELAY", "6"))}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # caller already gave up (timeout test)

    def do_GET(self):
        self._send(200, {"status": "ok", "provider": NAME, "mode": state["mode"]})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        if self.path == "/admin/mode":
            state["mode"] = json.loads(raw)["mode"]
            return self._send(200, {"provider": NAME, "mode": state["mode"]})

        mode = state["mode"]
        if mode == "500":
            return self._send(500, {"error": {"message": "simulated outage", "type": "server_error"}})
        if mode == "429":
            return self._send(429, {"error": {"message": "simulated rate limit", "type": "rate_limit"}})
        if mode == "timeout":
            time.sleep(state["delay"])

        self._send(200, {
            "id": f"mock-{NAME}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": f"mock-{NAME}",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": f"SELECT 1 -- served by {NAME}"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        })

    def log_message(self, fmt, *args):
        print(f"[{NAME}/{state['mode']}] {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()