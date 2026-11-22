"""speak: send io's spoken sentences to a phone over Wi-Fi (the audio route, see docs/decisions.md).

io serves a tiny web page on PORT. The phone, on the same Wi-Fi as the Pi, opens http://<pi address>:PORT/,
taps Start once (phones only speak after a tap), and the page speaks every sentence io sends over a
server-sent-events stream. A sentence is never cut off by an ordinary update: only warnings ("!")
interrupt; otherwise the newest sentence waits its turn. The page asks the phone to keep its screen on (wake
lock, when the browser allows it) and shows the connection state and last sentence.
"""
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8080
KEEPALIVE_S = 15  # an idle stream gets a comment this often so the phone's connection is not dropped

PAGE = b"""<!doctype html>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>iris</title>
<style>
body{font:22px sans-serif;margin:16px;text-align:center}
button{font-size:28px;padding:16px 28px;margin:8px}
select{font-size:22px;padding:10px;margin:8px;max-width:95%}
#status{font-size:40px;font-weight:bold;padding:16px;margin:12px 0;border-radius:12px;background:#ddd}
#status.ok{background:#8d8}#status.bad{background:#f99}
#last{font-size:44px;margin-top:24px;min-height:3em}
</style>
<div id=status>Not started</div>
<button id=go>Start speaking</button>
<button id=test>Test voice</button>
<div id=note></div>
<select id=voices></select>
<div id=hint></div>
<div id=last></div>
<script>
const $ = id => document.getElementById(id);
// A sentence is never cut off by an ordinary update: while one is being spoken the newest ordinary sentence
// waits (older waiting ones are dropped) and is spoken when it ends. Only warnings ("!") interrupt, and
// not another urgent sentence still being spoken.
let current = null, currentUrgent = false, pending = null;
// Every English voice the phone offers, best guess first. The listener picks one in the list (and hears it say a
// test sentence); the choice is remembered on the phone. "Natural" voices are network or downloaded ones:
// Google (Android), Siri/Premium/Enhanced (iPhone, downloaded in Settings > Accessibility > Spoken Content > Voices).
let voice = null, english = [];
const score = v => (/premium|enhanced|natural|neural|online|siri/i.test(v.name) ? 3 : 0)
  + (/google/i.test(v.name) ? 2 : 0) + (/ava|zoe|samantha|allison|nicky|serena|daniel|karen/i.test(v.name) ? 1 : 0)
  + (v.lang === "en-US" ? 1 : 0) + (v.localService ? 0 : 1);
const pickVoice = () => {
  english = speechSynthesis.getVoices().filter(v => v.lang.startsWith("en")).sort((a, b) => score(b) - score(a));
  voice = english.find(v => v.name === localStorage.getItem("voice")) || english[0] || null;
  $("voices").innerHTML = "";
  for (const v of english) $("voices").add(new Option(v.name + " (" + v.lang + ")", v.name));
  if (voice) $("voices").value = voice.name;
};
$("voices").onchange = () => {
  voice = english.find(v => v.name === $("voices").value);
  localStorage.setItem("voice", voice.name);
  speechSynthesis.cancel();
  current = null; pending = null;
  speak("Careful! A person in front of you, about two meters away");
};
speechSynthesis.onvoiceschanged = pickVoice;
pickVoice();
$("hint").textContent = "Pick the most natural voice in the list; it is remembered. On iPhone, download an Enhanced or Premium English voice in Settings > Accessibility > Spoken Content > Voices.";
const play = (text, urgent) => {
  const u = new SpeechSynthesisUtterance(text);
  if (voice) u.voice = voice;
  current = u; currentUrgent = urgent;
  const done = () => {
    if (current !== u) return;
    current = null;
    if (pending !== null) { const p = pending; pending = null; play(p, false); }
  };
  u.onend = done; u.onerror = done;
  speechSynthesis.speak(u);
};
const speak = text => {
  const urgent = text.includes("!");
  if (current === null) play(text, urgent);
  else if (urgent && !currentUrgent) { pending = null; speechSynthesis.cancel(); play(text, true); }
  else pending = text;
};
const status = (text, cls) => { $("status").textContent = text; $("status").className = cls; };
let started = false;
// navigator.wakeLock exists only in secure contexts; this page is plain http, so a browser may not offer it
const keepAwake = async () => {
  if (!navigator.wakeLock) { $("note").textContent = "No wake lock here: keep the screen on yourself."; return; }
  await navigator.wakeLock.request("screen");
};
document.addEventListener("visibilitychange", () => {
  if (started && document.visibilityState === "visible") keepAwake();
});
$("test").onclick = () => speak("Careful! A person in front of you, about two meters away");
$("go").onclick = async () => {
  started = true;
  speak("Ready");
  keepAwake();
  const es = new EventSource("/events");
  es.onopen = () => status("Connected", "ok");
  es.onerror = () => status("Reconnecting...", "bad");
  es.onmessage = e => { speak(e.data); $("last").textContent = e.data; };
  $("go").remove();
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
