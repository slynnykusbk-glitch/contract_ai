import types
from pathlib import Path

from word_addin_dev import serve_https_panel as shp


def test_parse_args_and_port(monkeypatch, tmp_path):
    called = {}

    def fake_bind(host, port, Handler, ctx):
        called["host"] = host
        called["port"] = port

        class Dummy:
            def serve_forever(self):
                raise KeyboardInterrupt

            def shutdown(self):
                pass

            def server_close(self):
                pass

        return Dummy()

    monkeypatch.setattr(shp, "_bind_https_server", fake_bind)
    monkeypatch.setattr(shp, "_ensure_certs", lambda *a, **k: None)
    monkeypatch.setattr(shp, "_build_ssl_context", lambda *a, **k: object())
    monkeypatch.setattr(
        shp.sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code))
    )

    args = ["--port", "4321", "--root", str(tmp_path)]
    try:
        shp.main(args)
    except SystemExit as e:
        assert e.code == 0
    assert called["port"] == 4321
    assert called["host"] == "127.0.0.1"
