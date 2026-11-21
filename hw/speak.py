"""speak: send io's spoken sentences to a phone over Wi-Fi (the audio route, see docs/decisions.md).

io serves a tiny web page on PORT. The phone, on the same Wi-Fi as the Pi, opens http://<pi address>:PORT/,
taps Start once (phones only speak after a tap), and the page speaks every sentence io sends over a
server-sent-events stream. A new sentence cancels the one still being spoken: the latest warning wins.
"""
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8080
KEEPALIVE_S = 15  # an idle stream gets a comment this often so the phone's connection is not dropped

PAGE = b"""<!doctype html>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>iris</title>
<style>body{font:22px sans-serif;margin:24px}button{font-size:28px;padding:16px 28px}#log{margin-top:24px;color:#444}</style>
<button id=go>Start speaking</button>
<div id=log></div>
<script>
document.getElementById("go").onclick = () => {
  speechSynthesis.speak(new SpeechSynthesisUtterance("Ready"));
  const es = new EventSource("/events");
  es.onmessage = e => {
    speechSynthesis.cancel();
    speechSynthesis.speak(new SpeechSynthesisUtterance(e.data));
    document.getElementById("log").textContent = e.data;
  };
  document.getElementById("go").remove();
};
</script>
"""


class PhoneSpeaker:
    def __init__(self, port=PORT):
        self._subscribers = []  # one queue per connected phone
        self._lock = threading.Lock()
        speaker = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(PAGE)))
                    self.end_headers()
                    self.wfile.write(PAGE)
                elif self.path == "/events":
                    speaker._stream(self)
                else:
                    self.send_error(404)

            def log_message(self, *args):  # no per-request lines on io's console
                pass

        self._server = ThreadingHTTPServer(("", port), Handler)  # binds now, so a port in use fails at startup

    def serve(self):
        self._server.serve_forever()

    def say(self, text):
        with self._lock:
            for q in self._subscribers:
                q.put(text)

    def _stream(self, handler):
        q = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        try:
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.send_header("Cache-Control", "no-cache")
            handler.end_headers()
            while True:
                try:
                    handler.wfile.write(f"data: {q.get(timeout=KEEPALIVE_S)}\n\n".encode())
                except queue.Empty:
                    handler.wfile.write(b": keepalive\n\n")
                handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the phone went away: normal at a network boundary, not a failure
        finally:
            with self._lock:
                self._subscribers.remove(q)
