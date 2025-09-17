import http.server, ssl, os
from urllib.parse import unquote

ROOT  = r"C:\Users\Ludmila\contract_ai\word_addin_dev"
PANEL = os.path.join(ROOT, "panel")      # здесь taskpane.html, commands.html и /assets
CRT   = r"C:\Users\Ludmila\contract_ai\dev\localhost.crt"
KEY   = r"C:\Users\Ludmila\contract_ai\dev\localhost.key"

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        p = unquote(self.path)
        if p == "/health":
            self.send_response(200); self.end_headers(); self.wfile.write(b"OK"); return
        if p in ("/", "/panel", "/panel/"):
            p = "/panel/taskpane.html"
        if p.startswith("/panel/") or p.startswith("/assets/") or p.startswith("/api-client/"):
            rel = p.lstrip("/")
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                path = os.path.join(PANEL, rel.replace("panel/",""))
            if os.path.isdir(path):
                path = os.path.join(path, "index.html")
            if not os.path.exists(path):
                self.send_error(404, "Not Found"); return
            self.path = path
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        self.send_error(404, "Not Found")

if __name__ == "__main__":
    os.chdir(ROOT)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 9443), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CRT, KEY)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print("Serving https://127.0.0.1:9443  (Ctrl+C to stop)")
    httpd.serve_forever()
