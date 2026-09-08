from __future__ import annotations

import html
import json
import os
import platform
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


STARTED = time.monotonic()
PORT = int(os.getenv("PORT", "8080"))


def status() -> dict[str, object]:
    return {
        "status": "online",
        "hostname": socket.gethostname(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "uptime_seconds": round(time.monotonic() - STARTED, 1),
        "powered_by": "Repo2Box",
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send("application/json", json.dumps(status()).encode())
            return
        if self.path != "/":
            self.send_error(404)
            return
        data = status()
        cards = "".join(
            f"<article><span>{html.escape(key.replace('_', ' ').title())}</span>"
            f"<strong>{html.escape(str(value))}</strong></article>"
            for key, value in data.items()
            if key not in {"status", "powered_by"}
        )
        page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="5">
  <title>Repo2Box is alive</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; color:#e9fbff;
      background:radial-gradient(circle at 15% 20%,#174b52 0,transparent 32%),#07151c; }}
    main {{ width:min(900px,90vw); }}
    .pill {{ display:inline-flex; gap:.55rem; align-items:center; padding:.45rem .8rem;
      border:1px solid #2dd4bf55; border-radius:999px; color:#7eeadf; background:#0d2a30; }}
    .dot {{ width:.55rem; height:.55rem; border-radius:50%; background:#2dd4bf; box-shadow:0 0 18px #2dd4bf; }}
    h1 {{ max-width:750px; font-size:clamp(2.6rem,7vw,5.8rem); line-height:.95; margin:1.4rem 0; letter-spacing:-.055em; }}
    h1 em {{ color:#2dd4bf; font-style:normal; }}
    p {{ color:#9cc3ca; font-size:1.1rem; max-width:600px; }}
    section {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:1rem; margin-top:2.5rem; }}
    article {{ padding:1.1rem; border:1px solid #274650; border-radius:14px; background:#0b2029cc; }}
    article span {{ display:block; color:#7d9da5; font-size:.75rem; text-transform:uppercase; letter-spacing:.12em; }}
    article strong {{ display:block; margin-top:.55rem; overflow-wrap:anywhere; }}
    footer {{ margin-top:2.5rem; color:#5d7f87; }}
  </style>
</head>
<body><main>
  <div class="pill"><span class="dot"></span> Device online</div>
  <h1>This repository became a <em>device.</em></h1>
  <p>A zero-dependency Python app, detected and packaged automatically for Raspberry Pi 4 and 5.</p>
  <section>{cards}</section>
  <footer>Repo2Box alpha · refreshes every 5 seconds</footer>
</main></body></html>"""
        self._send("text/html; charset=utf-8", page.encode())

    def _send(self, content_type: str, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


if __name__ == "__main__":
    print(f"Repo2Box demo listening on http://0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
