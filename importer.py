#!/usr/bin/env python3
"""Importa as planilhas XLS legadas para um indice SQLite pesquisavel."""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import subprocess
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "docs"
DB_PATH = ROOT / "data" / "acervo.sqlite3"

ASCOM_FIELDS = [
    "Número de identificação",
    "Assunto do negativo",
    "Convidado / indexador",
    "Resumo descritivo",
    "Data",
    "Observações técnicas",
    "Número de identificação (sistema)",
    "Gestão",
    "Dossiê",
    "Número do item",
    "Inserido no sistema / pessoa",
    "Número corrente",
]

GR1014_FIELDS = [
    "Natureza do suporte",
    "Descrição",
    "Data",
    "Depósito",
    "Tipo de móvel",
    "Módulo / estante",
    "Face",
    "Gaveta / prateleira",
    "Número da caixa",
    "Número do envelope",
    "Campo auxiliar",
    "Agrupamento",
    "Campo auxiliar 2",
    "Pendência",
]

GR1521_FIELDS = [
    "Descrição",
    "Complemento 1",
    "Complemento 2",
    "Complemento 3",
    "Suporte",
    "Gênero",
    "Quantidade",
    "Data limite",
    "Depósito",
    "Tipo de móvel",
    "Número do móvel",
    "Posição",
    "Tipo de embalagem",
    "Número da embalagem",
]


def clean(value: str) -> str:
    return " ".join((value or "").replace("\x00", "").split())


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch)).casefold()


def read_xls(path: Path) -> list[list[str]]:
    try:
        result = subprocess.run(
            ["xls2csv", "-s", "cp1252", "-d", "utf-8", str(path)],
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "O programa 'xls2csv' não foi encontrado. Instale o pacote catdoc e tente novamente."
        ) from exc
    return [[clean(cell) for cell in row] for row in csv.reader(result.stdout.splitlines())]


def extract_year(*values: str) -> int | None:
    for value in values:
        match = re.search(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2})(?!\d)", value or "")
        if match:
            return int(match.group(1))
    return None


def raw_fields(headers: list[str], row: list[str]) -> dict[str, str]:
    data = {}
    for index, value in enumerate(row):
        if not value:
            continue
        label = headers[index] if index < len(headers) else f"Campo {index + 1}"
        if label in data:
            label = f"{label} ({index + 1})"
        data[label] = value
    return data


def make_record(
    *, source: str, source_row: int, collection: str, identifier: str = "",
    title: str = "", description: str = "", date_text: str = "", creator: str = "",
    management: str = "", dossier: str = "", item_number: str = "", support: str = "",
    genre: str = "", location: str = "", notes: str = "", fields: dict[str, str],
) -> dict:
    searchable = " ".join(fields.values())
    return {
        "source_file": source,
        "source_row": source_row,
        "collection": collection,
        "identifier": identifier,
        "title": title,
        "description": description,
        "date_text": date_text,
        "year": extract_year(date_text, title, description),
        "creator": creator,
        "management": management,
        "dossier": dossier,
        "item_number": item_number,
        "support": support,
        "genre": genre,
        "location": location,
        "notes": notes,
        "raw_json": json.dumps(fields, ensure_ascii=False),
        "search_text": normalized(searchable),
    }


def parse_ascom(path: Path, rows: list[list[str]]):
    for row_number, row in enumerate(rows[1:], 2):
        padded = (row + [""] * 12)[:12]
        if not any(padded):
            continue
        fields = raw_fields(ASCOM_FIELDS, padded)
        yield make_record(
            source=path.name,
            source_row=row_number,
            collection="Acervo fotográfico ASCOM",
            identifier=padded[0] or padded[6],
            title=padded[1] or "Registro fotográfico",
            creator=padded[2],
            description=padded[3],
            date_text=padded[4],
            notes=padded[5],
            management=padded[7],
            dossier=padded[8],
            item_number=padded[9],
            fields=fields,
        )


def parse_gr1014(path: Path, rows: list[list[str]]):
    for row_number, row in enumerate(rows[7:], 8):
        padded = (row + [""] * 14)[:14]
        if not any(padded[:12]):
            continue
        fields = raw_fields(GR1014_FIELDS, padded)
        location_parts = [
            f"{GR1014_FIELDS[index]}: {padded[index]}"
            for index in range(3, 10) if padded[index]
        ]
        yield make_record(
            source=path.name,
            source_row=row_number,
            collection="Guia de recolhimento 1014",
            identifier=padded[9],
            title=padded[1] or "Documento sem descrição",
            description=padded[1],
            date_text=padded[2],
            support=padded[0],
            location=" · ".join(location_parts),
            notes=" · ".join(value for value in padded[11:14] if value),
            fields=fields,
        )


def parse_gr1521(path: Path, rows: list[list[str]]):
    last_description = ""
    for row_number, row in enumerate(rows[12:], 13):
        padded = (row + [""] * 14)[:14]
        if not any(padded):
            continue
        if padded[0]:
            last_description = padded[0]
        description = padded[0] or last_description
        fields = raw_fields(GR1521_FIELDS, padded)
        if not padded[0] and description:
            fields = {"Descrição (continuação do item anterior)": description, **fields}
        location_parts = [
            f"{GR1521_FIELDS[index]}: {padded[index]}"
            for index in range(8, 14) if padded[index]
        ]
        identifier_match = re.match(r"\s*([\d.]+)\s*:", description)
        yield make_record(
            source=path.name,
            source_row=row_number,
            collection="Guia de recolhimento 1521",
            identifier=identifier_match.group(1) if identifier_match else padded[13],
            title=description or "Item da guia 1521",
            description=description,
            date_text=padded[7],
            support=padded[4],
            genre=padded[5],
            location=" · ".join(location_parts),
            fields=fields,
        )


def records_from(path: Path):
    rows = read_xls(path)
    if path.name.startswith("LISTA_ASCOM_"):
        return parse_ascom(path, rows)
    if path.name == "gr1014_negativos.xls":
        return parse_gr1014(path, rows)
    if path.name == "GR 1521.xls":
        return parse_gr1521(path, rows)
    return iter(())


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE records (
    id INTEGER PRIMARY KEY,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    collection TEXT NOT NULL,
    identifier TEXT,
    title TEXT NOT NULL,
    description TEXT,
    date_text TEXT,
    year INTEGER,
    creator TEXT,
    management TEXT,
    dossier TEXT,
    item_number TEXT,
    support TEXT,
    genre TEXT,
    location TEXT,
    notes TEXT,
    raw_json TEXT NOT NULL,
    search_text TEXT NOT NULL
);
CREATE INDEX idx_records_collection ON records(collection);
CREATE INDEX idx_records_year ON records(year);
CREATE INDEX idx_records_identifier ON records(identifier);
CREATE VIRTUAL TABLE records_fts USING fts5(
    search_text, content='records', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER records_ai AFTER INSERT ON records BEGIN
    INSERT INTO records_fts(rowid, search_text) VALUES (new.id, new.search_text);
END;
"""


def build_database(docs_dir: Path = DOCS_DIR, db_path: Path = DB_PATH) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = db_path.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    connection.executescript(SCHEMA)
    columns = [
        "source_file", "source_row", "collection", "identifier", "title", "description",
        "date_text", "year", "creator", "management", "dossier", "item_number", "support",
        "genre", "location", "notes", "raw_json", "search_text",
    ]
    placeholders = ",".join("?" for _ in columns)
    total = 0
    for path in sorted(docs_dir.glob("*.xls")):
        before = total
        for record in records_from(path):
            connection.execute(
                f"INSERT INTO records ({','.join(columns)}) VALUES ({placeholders})",
                [record[column] for column in columns],
            )
            total += 1
        print(f"{path.name}: {total - before} registros")
    connection.commit()
    connection.execute("PRAGMA optimize")
    connection.close()
    temporary.replace(db_path)
    print(f"Índice criado em {db_path} com {total} registros.")
    return total


if __name__ == "__main__":
    try:
        build_database()
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, file=sys.stderr)
        raise SystemExit(1) from exc
