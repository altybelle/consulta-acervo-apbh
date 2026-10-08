#!/usr/bin/env python3
"""Servidor HTTP local para consulta do inventario arquivistico."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from importer import DB_PATH, ROOT, build_database, normalized


STATIC_DIR = ROOT / "static"
PUBLIC_COLUMNS = """id, source_file, source_row, collection, identifier, title,
description, date_text, year, creator, management, dossier, item_number, support,
genre, location, notes"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def fts_query(query: str) -> str:
    words = re.findall(r"[\wÀ-ÿ]+", normalized(query), flags=re.UNICODE)
    return " AND ".join(f'"{word}"*' for word in words[:12])


def search(params: dict[str, list[str]]) -> dict:
    query = params.get("q", [""])[0].strip()
    collection = params.get("collection", [""])[0].strip()
    year_from = params.get("year_from", [""])[0].strip()
    year_to = params.get("year_to", [""])[0].strip()
    try:
        page = max(1, int(params.get("page", ["1"])[0]))
    except ValueError:
        page = 1
    limit = 20
    clauses, values = [], []
    join = ""
    if query:
        expression = fts_query(query)
        if expression:
            join = "JOIN records_fts ON records_fts.rowid = records.id"
            clauses.append("records_fts MATCH ?")
            values.append(expression)
    if collection:
        clauses.append("records.collection = ?")
        values.append(collection)
    if year_from.isdigit():
        clauses.append("records.year >= ?")
        values.append(int(year_from))
    if year_to.isdigit():
        clauses.append("records.year <= ?")
        values.append(int(year_to))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "ORDER BY bm25(records_fts), records.id" if query and join else "ORDER BY records.id"
    with connect() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM records {join} {where}", values
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM records {join} {where} {order} LIMIT ? OFFSET ?",
            [*values, limit, (page - 1) * limit],
        ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "page": page, "limit": limit}


class Handler(BaseHTTPRequestHandler):
    server_version = "AcervoBH/1.0"

    def json_response(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            try:
                with connect() as connection:
                    connection.execute("SELECT 1").fetchone()
                return self.json_response({"status": "ok"})
            except sqlite3.Error:
                return self.json_response({"status": "error"}, HTTPStatus.SERVICE_UNAVAILABLE)
        if parsed.path == "/api/search":
            return self.json_response(search(parse_qs(parsed.query)))
        if parsed.path == "/api/stats":
            with connect() as connection:
                total = connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
                sources = [dict(row) for row in connection.execute(
                    "SELECT collection, COUNT(*) AS count FROM records GROUP BY collection ORDER BY collection"
                )]
                years = connection.execute(
                    "SELECT MIN(year), MAX(year) FROM records WHERE year IS NOT NULL"
                ).fetchone()
            return self.json_response({"total": total, "collections": sources, "year_min": years[0], "year_max": years[1]})
        match = re.fullmatch(r"/api/records/(\d+)", parsed.path)
        if match:
            with connect() as connection:
                row = connection.execute(
                    f"SELECT {PUBLIC_COLUMNS}, raw_json FROM records WHERE id = ?", (match.group(1),)
                ).fetchone()
            if not row:
                return self.json_response({"error": "Registro não encontrado"}, HTTPStatus.NOT_FOUND)
            record = dict(row)
            record["fields"] = json.loads(record.pop("raw_json"))
            return self.json_response(record)
        return self.serve_static(parsed.path)

    def serve_static(self, request_path: str):
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        path = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in path.parents or not path.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


def main():
    if not DB_PATH.exists():
        print("Índice ausente; importando as planilhas...")
        build_database()
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1")
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError:
        raise SystemExit("A variável PORT precisa conter um número inteiro.")
    server = ThreadingHTTPServer((host, port), Handler)
    public_host = "127.0.0.1" if host == "0.0.0.0" else host
    print(f"Acervo disponível em http://{public_host}:{port}")
    print("Pressione Ctrl+C para encerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
