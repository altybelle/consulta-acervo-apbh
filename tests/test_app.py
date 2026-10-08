import json
import tempfile
import unittest
from pathlib import Path

import importer
import server


class ImporterTests(unittest.TestCase):
    def test_year_extraction(self):
        self.assertEqual(importer.extract_year("1968.12.??"), 1968)
        self.assertEqual(importer.extract_year("Evento em 07/05/1993"), 1993)
        self.assertIsNone(importer.extract_year("s/d"))

    def test_fts_query_is_normalized_and_prefixed(self):
        self.assertEqual(server.fts_query("Praça São José"), '"praca"* AND "sao"* AND "jose"*')

    def test_ascom_mapping(self):
        rows = [["cabecalho"], ["42", "Praça", "Ana", "Descrição", "1968.01.02"]]
        record = next(importer.parse_ascom(Path("LISTA_ASCOM_00000.xls"), rows))
        self.assertEqual(record["identifier"], "42")
        self.assertEqual(record["year"], 1968)
        self.assertIn("Descrição", json.loads(record["raw_json"])["Resumo descritivo"])

    def test_static_assets_exist(self):
        self.assertTrue((server.STATIC_DIR / "index.html").is_file())
        self.assertTrue((server.STATIC_DIR / "app.js").is_file())
        self.assertTrue((server.STATIC_DIR / "styles.css").is_file())


if __name__ == "__main__":
    unittest.main()
