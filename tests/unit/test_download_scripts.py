from __future__ import annotations

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import httpx
import pytest
from typing_extensions import override

from scripts.download_corpus import CorpusItem, download
from scripts.download_t2ragbench_subset import json_lines

BODY = b'{"id": 1, "text": "a\xe2\x80\xa8b"}\n\n{"id": 2}'


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "/data")
            self.end_headers()
        elif self.path == "/missing":
            self.send_response(404)
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY)

    @override
    def log_message(self, format: str, *args: object) -> None:
        return None


@pytest.fixture
def base_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_json_lines_split_only_on_newline_bytes(base_url: str) -> None:
    assert list(json_lines(f"{base_url}/data")) == [
        b'{"id": 1, "text": "a\xe2\x80\xa8b"}',
        b"",
        b'{"id": 2}',
    ]


def test_download_follows_a_redirect_and_writes_the_body(base_url: str, tmp_path: Path) -> None:
    item = CorpusItem("corpus.bin", f"{base_url}/moved", "test")
    assert download(item, tmp_path).read_bytes() == BODY


def test_download_fails_on_an_error_status(base_url: str, tmp_path: Path) -> None:
    item = CorpusItem("corpus.bin", f"{base_url}/missing", "test")
    with pytest.raises(httpx.HTTPStatusError):
        download(item, tmp_path)
    assert not (tmp_path / "corpus.bin").exists()
