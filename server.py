#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
기후로운 경제생활 뉴스 모니터링 — 로컬 서버
실행: python server.py
접속: http://localhost:8000
"""

import glob
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8000
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_news.py")


def latest_html():
    """news_YYYYMMDD.html 중 가장 최신 파일 경로 반환"""
    files = sorted(
        glob.glob(os.path.join(os.path.dirname(SCRIPT), "news_*.html")),
        reverse=True,
    )
    return files[0] if files else None


class Handler(BaseHTTPRequestHandler):

    # ── GET ──────────────────────────────────────────────────
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            path = latest_html()
            if not path:
                body = (
                    "<h2>뉴스 파일이 없습니다</h2>"
                    "<p><code>python fetch_news.py</code>를 먼저 실행해주세요.</p>"
                ).encode("utf-8")
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return

            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        else:
            self.send_error(404, "Not Found")

    # ── POST ─────────────────────────────────────────────────
    def do_POST(self):
        if self.path == "/refresh":
            self._run_refresh()
        else:
            self.send_error(404, "Not Found")

    def _run_refresh(self):
        print("[server] fetch_news.py 실행 중…", flush=True)
        try:
            result = subprocess.run(
                [sys.executable, SCRIPT],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=os.path.dirname(SCRIPT),
            )
            ok  = result.returncode == 0
            msg = result.stderr.strip() if not ok else "완료"
            print(f"[server] {'완료' if ok else '실패'}: {result.returncode}", flush=True)
            if not ok:
                print(result.stderr[-800:], flush=True)
        except subprocess.TimeoutExpired:
            ok  = False
            msg = "timeout (600s 초과)"
            print("[server] timeout", flush=True)
        except Exception as e:
            ok  = False
            msg = str(e)
            print(f"[server] 예외: {e}", flush=True)

        body = json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if ok else 500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    # ── 로그 간소화 ───────────────────────────────────────────
    def log_message(self, fmt, *args):
        print(f"  [{self.address_string()}] {fmt % args}", flush=True)


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = HTTPServer(("", PORT), Handler)
    print(f"서버 시작 → http://localhost:{PORT}")
    print("종료: Ctrl+C\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료")
        server.server_close()
