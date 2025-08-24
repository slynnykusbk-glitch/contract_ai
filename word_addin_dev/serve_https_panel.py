#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import ssl
import socket
import signal
import datetime
import mimetypes
import subprocess
import platform
from ipaddress import IPv4Address, IPv6Address
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from functools import partial

# ---------------------------
# MIME types (ensure .js etc.)
# ---------------------------
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("text/html", ".html")
mimetypes.add_type("text/plain", ".map")


def _ensure_cryptography() -> None:
    """
    Ensure 'cryptography' is importable. If not, try installing it once.
    Exit with code 3 if it cannot be installed.
    """
    try:
        import cryptography  # noqa: F401
        return
    except Exception:
        pass

    print("cryptography not found; attempting installation…", file=sys.stderr)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "cryptography>=42"],
            check=True,
        )
    except Exception as e:
        print(f"failed to install cryptography: {e}", file=sys.stderr)
        print("please install with: python -m pip install 'cryptography>=42'", file=sys.stderr)
        sys.exit(3)

    # Retry import
    try:
        import cryptography  # noqa: F401
    except Exception as e:
        print(f"cryptography still unavailable after install: {e}", file=sys.stderr)
        sys.exit(3)


def _generate_self_signed(cert_path: Path, key_path: Path, hostnames: list[str]) -> None:
    """
    Generate a self-signed certificate using cryptography.
    Auto-installs cryptography if missing.
    """
    _ensure_cryptography()
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except Exception as e:
        print(f"unable to import cryptography after install: {e}", file=sys.stderr)
        sys.exit(3)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "GB"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "England"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "London"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ContractAI"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0] if hostnames else "localhost"),
        ]
    )

    # Subject Alternative Names for localhost development (with proper IPAddress entries)
    sans = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(IPv4Address("127.0.0.1")),
        x509.IPAddress(IPv6Address("::1")),
    ])

    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=3650))  # ~10 years
        .add_extension(sans, critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    try:
        os.chmod(key_path, 0o600)
    except Exception:
        pass

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def _try_trust_windows_root(cert_path: Path) -> None:
    """
    On Windows, attempt to add the dev certificate to the Current User Trusted Root store.
    Uses certutil -user -addstore Root <cert>. Never fails the server on error.
    """
    try:
        if platform.system().lower() != "windows":
            return
        # Ensure certutil exists
        where = subprocess.run(
            ["where", "certutil"],
            capture_output=True,
            text=True,
        )
        if where.returncode != 0:
            print("certutil not found on PATH; skipping auto-trust.", file=sys.stderr)
            return

        cmd = ["certutil", "-user", "-addstore", "Root", str(cert_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            # Success (0x00000000)
            msg = "certificate added to CurrentUser\\Root store"
            print(f"auto-trust: {msg}", file=sys.stderr)
        else:
            # Non-zero: print hint, do not terminate
            hint = (
                "auto-trust failed; you may need to trust the certificate manually or continue and accept the TLS warning in the browser."
            )
            print(
                f"auto-trust warning (exit={proc.returncode}): {hint}\nstdout: {proc.stdout}\nstderr: {proc.stderr}",
                file=sys.stderr,
            )
    except Exception as e:
        print(f"auto-trust exception (ignored): {e}", file=sys.stderr)


def _ensure_certs(cert_path: Path, key_path: Path, host: str, regen: bool) -> bool:
    """
    Ensure certificates exist. Returns True if (re)generated in this call.
    """
    regenerated = False
    if regen:
        try:
            if cert_path.exists():
                cert_path.unlink()
            if key_path.exists():
                key_path.unlink()
        except Exception:
            pass

    if not cert_path.exists() or not key_path.exists():
        _generate_self_signed(cert_path, key_path, [host])
        regenerated = True

    # Attempt auto-trust on Windows after generation (or always try harmlessly)
    _try_trust_windows_root(cert_path)
    return regenerated


class NoCacheHandler(SimpleHTTPRequestHandler):
    # Use default logging to stderr; RUN_DEV waits only for the single READY line we print in main.

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def guess_type(self, path):
        # Ensure correct JS MIME on some Windows/Python combos
        typ = mimetypes.guess_type(path)[0]
        if not typ:
            # Fallbacks
            if path.endswith(".js"):
                return "application/javascript"
            if path.endswith(".css"):
                return "text/css"
            if path.endswith(".json"):
                return "application/json"
            if path.endswith(".html"):
                return "text/html"
            return "application/octet-stream"
        return typ

    def _maybe_redirect_legacy(self) -> bool:
        """
        Redirect old pinned build paths to live assets:
          /app/build-*/taskpane.html           -> /taskpane.html
          /app/build-*/taskpane.bundle.js[*]  -> /taskpane.bundle.js (preserve ?v=...)
        """
        p = urlparse(self.path)
        path = p.path or "/"
        # Redirect old taskpane.html path
        if path.startswith("/app/build-") and path.endswith("/taskpane.html"):
            target = "/taskpane.html"
            self.send_response(301)
            self.send_header("Location", target)
            self.end_headers()
            return True
        # Redirect old bundle path (preserve query, e.g., ?v=...)
        if path.startswith("/app/build-") and "taskpane.bundle.js" in path:
            target = "/taskpane.bundle.js"
            if p.query:
                target = f"{target}?{p.query}"
            self.send_response(301)
            self.send_header("Location", target)
            self.end_headers()
            return True
        return False

    def do_GET(self):
        # Log full Request-URL for debugging
        try:
            host = self.headers.get("Host") or f"{self.server.server_address[0]}:{self.server.server_address[1]}"
            sys.stderr.write(f"[REQ] https://{host}{self.path}\n")
            sys.stderr.flush()
        except Exception:
            pass
        if self._maybe_redirect_legacy():
            return
        return super().do_GET()


def _build_ssl_context(cert_file: Path, key_file: Path) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.set_ciphers(
            "ECDHE+AESGCM:ECDHE+CHACHA20:RSA+AESGCM:!aNULL:!MD5:!DSS"
        )
    except Exception:
        # use defaults if cipher set fails on older OpenSSL
        pass
    ctx.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
    return ctx


def _bind_https_server(host: str, port: int, handler_cls, ssl_ctx: ssl.SSLContext):
    # Use bind_and_activate=False to wrap socket before activate.
    httpd = ThreadingHTTPServer((host, port), handler_cls, bind_and_activate=False)
    # Allow quick restarts
    httpd.allow_reuse_address = True
    try:
        httpd.server_bind()
    except OSError as e:
        # Port busy or permission denied
        msg = str(e).lower()
        if "address already in use" in msg or "permission denied" in msg or getattr(e, "winerror", None) in (10013, 10048):
            print(f"port {port} busy", file=sys.stderr)
            sys.exit(2)
        raise
    # Wrap with TLS
    httpd.socket = ssl_ctx.wrap_socket(httpd.socket, server_side=True)
    httpd.server_activate()
    return httpd


def main(argv=None):
    parser = argparse.ArgumentParser(description="HTTPS static server for Office Taskpane panel (dev)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3000, help="Bind port (default 3000)")
    default_root = Path(__file__).resolve().parent
    parser.add_argument("--root", default=str(default_root), help="Static root (default: script directory)")
    parser.add_argument("--cert", default=str(default_root / "certs" / "panel-cert.pem"), help="Path to certificate PEM")
    parser.add_argument("--key", default=str(default_root / "certs" / "panel-key.pem"), help="Path to private key PEM")
    parser.add_argument("--regen-cert", action="store_true", help="Force regenerate self-signed certificate")
    args = parser.parse_args(argv)

    host = args.host
    port = int(args.port)
    root = Path(args.root).resolve()
    cert_path = Path(args.cert).resolve()
    key_path = Path(args.key).resolve()

    if not root.exists():
        print(f"root does not exist: {root}", file=sys.stderr)
        sys.exit(1)

    # Ensure certificates exist (or regenerate if requested)
    try:
        _ensure_certs(cert_path, key_path, host, args.regen_cert)
    except SystemExit:
        raise
    except Exception as e:
        print(f"failed to ensure certificates: {e}", file=sys.stderr)
        sys.exit(1)

    # Build SSL context; if invalid cert/key and user wants regen, suggest it
    try:
        ssl_ctx = _build_ssl_context(cert_path, key_path)
    except Exception as e:
        if not args.regen_cert:
            print(f"certificate or key invalid. Run with --regen-cert to recreate. Details: {e}", file=sys.stderr)
        else:
            print(f"failed to load regenerated certificate/key: {e}", file=sys.stderr)
        sys.exit(1)

    # Prepare handler with fixed root
    Handler = partial(NoCacheHandler, directory=str(root))

    # Bind HTTPS server
    try:
        httpd = _bind_https_server(host, port, Handler, ssl_ctx)
    except SystemExit:
        raise
    except Exception as e:
        msg = str(e).lower()
        if "address already in use" in msg or getattr(e, "winerror", None) in (10013, 10048):
            print(f"port {port} busy", file=sys.stderr)
            sys.exit(2)
        print(f"failed to bind HTTPS server: {e}", file=sys.stderr)
        sys.exit(1)

    # Graceful shutdown
    def _graceful_shutdown(signum, frame):
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass
        sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _graceful_shutdown)
        except Exception:
            pass

    # Ready line (single line expected by RUN_DEV)
    print(f"PANEL HTTPS READY https://{host}:{port}/ (root={root})", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _graceful_shutdown(signal.SIGINT, None)
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
