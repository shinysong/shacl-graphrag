"""Offline connector behavior; PostgreSQL transaction checks use a fake connection."""
import io
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from rule_workbench.connectors import read_file, list_db_tables, read_db_table
from rule_workbench.extractors import candidate_rules, extract_document


class FileTests(unittest.TestCase):
    def test_csv_identifiers_null_and_source(self):
        table = read_file("../../accounts.csv", b"id,name\n001,\n002,Ada\n")[0]
        self.assertEqual(table["rows"], [{"id": "001", "name": None}, {"id": "002", "name": "Ada"}])
        self.assertEqual(table["source"]["file"], "accounts.csv")
        self.assertEqual(len(table["source"]["sha256"]), 64)
        self.assertFalse(table["source"]["truncated"])

    def test_cp949(self):
        table = read_file("a.csv", "번호,이름\n001,홍길동\n".encode("cp949"))[0]
        self.assertEqual(table["rows"][0]["번호"], "001")

    def test_duplicate_and_ragged_headers(self):
        for payload in [b"id,id\n1,2", b"id,name\n1,2,3", b",name\n1,2"]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                read_file("a.csv", payload)

    def test_row_cap_exact_and_sentinel(self):
        for size in [5000, 5001]:
            table = read_file("a.csv", ("id\n" + "001\n" * size).encode())[0]
            self.assertEqual(len(table["rows"]), 5000)
            self.assertEqual(table["source"]["truncated"], size == 5001)

    def test_upload_and_columns_caps(self):
        with patch("rule_workbench.connectors.MAX_UPLOAD", 8), self.assertRaises(ValueError):
            read_file("a.csv", b"123456789")
        with self.assertRaises(ValueError):
            read_file("a.csv", (",".join(f"c{n}" for n in range(201)) + "\n").encode())

    def test_xlsx_all_sheets_dates_formulas(self):
        from openpyxl import Workbook

        book = Workbook()
        sheet = book.active
        sheet.title = "People"
        sheet.append(["id", "date", "expression"])
        sheet.append(["001", datetime(2026, 10, 17), "=1+1"])
        book.create_sheet("Other").append(["id"])
        payload = io.BytesIO()
        book.save(payload)
        tables = read_file("a.xlsx", payload.getvalue())
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0]["source"]["sheet"], "People")
        self.assertEqual(tables[0]["rows"][0]["date"], "2026-10-17T00:00:00")
        self.assertEqual(tables[0]["rows"][0]["expression"], "=1+1")
        self.assertEqual(tables[1]["rows"], [])
        with patch("rule_workbench.connectors.MAX_UNCOMPRESSED", 1), self.assertRaises(ValueError):
            read_file("a.xlsx", payload.getvalue())

    def test_sqlite_quoted_identifiers_views_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            connection = sqlite3.connect(path)
            connection.execute('CREATE TABLE "odd""name" (id TEXT, amount INTEGER)')
            connection.execute('INSERT INTO "odd""name" VALUES (?, ?)', ("001", 10))
            connection.execute('CREATE VIEW ignored AS SELECT * FROM "odd""name"')
            connection.commit()
            connection.close()
            tables = read_file("a.db", path.read_bytes())
            self.assertEqual(len(tables), 1)
            self.assertEqual(tables[0]["name"], 'odd"name')
            self.assertEqual(tables[0]["rows"], [{"id": "001", "amount": 10}])
            self.assertNotIn("url", tables[0]["source"])

    def test_sqlite_blob_and_bad_file(self):
        with self.assertRaises(ValueError):
            read_file("a.db", b"not a database")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE blobs (value BLOB)")
                connection.execute("INSERT INTO blobs VALUES (?)", (b"binary",))
            with self.assertRaises(ValueError):
                read_file("a.sqlite3", path.read_bytes())


class PostgreSQLTests(unittest.TestCase):
    def setup_connection(self):
        engine = MagicMock()
        connection = engine.connect.return_value.__enter__.return_value
        connection.execution_options.return_value = connection
        return engine, connection

    def test_readonly_and_quoted_query_without_credentials(self):
        engine, connection = self.setup_connection()
        result = MagicMock()
        result.keys.return_value = ["id"]
        result.__iter__.return_value = iter([("001",)])
        connection.execute.return_value = result
        connection.dialect.identifier_preparer.quote_identifier.return_value = '"odd""name"'
        inspector = MagicMock()
        inspector.get_table_names.return_value = ['odd"name']
        with patch("rule_workbench.connectors._engine", return_value=engine), patch("sqlalchemy.inspect", return_value=inspector):
            table = read_db_table("postgresql://person:SECRET@host/db", 'odd"name')
        statements = [str(call.args[0]) for call in connection.execute.call_args_list]
        self.assertEqual(statements[0], "SET TRANSACTION READ ONLY")
        self.assertIn("statement_timeout", statements[1])
        self.assertEqual(statements[-1], 'SELECT * FROM "odd""name" LIMIT 5001')
        self.assertNotIn("SECRET", str(table))
        self.assertEqual(table["rows"], [{"id": "001"}])
        engine.dispose.assert_called_once()
        result.close.assert_called_once()

    def test_error_does_not_expose_credentials_and_disposes(self):
        engine, connection = self.setup_connection()
        connection.execute.side_effect = RuntimeError("password=SECRET")
        with patch("rule_workbench.connectors._engine", return_value=engine):
            with self.assertRaises(ValueError) as error:
                list_db_tables("postgresql://person:SECRET@host/db")
        self.assertNotIn("SECRET", str(error.exception))
        engine.dispose.assert_called_once()

    def test_unknown_identifier_never_queried(self):
        engine, connection = self.setup_connection()
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["allowed"]
        with patch("rule_workbench.connectors._engine", return_value=engine), patch("sqlalchemy.inspect", return_value=inspector):
            with self.assertRaises(ValueError):
                read_db_table("postgresql://host/db", "allowed; DROP TABLE allowed")
        self.assertFalse(any("SELECT" in str(c.args[0]) for c in connection.execute.call_args_list))

    def test_only_postgres_and_no_libpq_options(self):
        for url in ["sqlite:///secret", "postgresql://host/db?passfile=/secret", "not a url"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                list_db_tables(url)


class DocumentTests(unittest.TestCase):
    def test_markdown_exact_source_and_unconfirmed_mapping(self):
        document = extract_document("rules.md", b"# Rules\n\n  ID must exist.  \n")
        rule = candidate_rules(document)[1]
        self.assertEqual(rule["source"], {"file": "rules.md", "line": 3, "quote": "  ID must exist.  "})
        self.assertEqual(rule["text"], rule["source"]["quote"])
        self.assertEqual((rule["status"], rule["table"], rule["column"]), ("draft", "", ""))

    def test_pdf_page_and_line_provenance(self):
        reader = MagicMock()
        reader.is_encrypted = False
        first, second = MagicMock(), MagicMock()
        first.extract_text.return_value = "Rule one\n\nRule two"
        second.extract_text.return_value = "Rule three"
        reader.pages = [first, second]
        with patch("pypdf.PdfReader", return_value=reader):
            document = extract_document("policy.pdf", b"fake PDF")
        rules = candidate_rules(document)
        self.assertEqual(rules[1]["source"]["page"], 1)
        self.assertEqual(rules[1]["source"]["line"], 3)
        self.assertEqual(rules[2]["source"]["page"], 2)

    def test_empty_no_ocr_and_caps(self):
        with self.assertRaisesRegex(ValueError, "OCR"):
            extract_document("empty.md", b" \n")
        with self.assertRaisesRegex(ValueError, "2,000 lines"):
            extract_document("long.md", b"rule\n" * 2001)
        document = extract_document("rules.md", b"rule\n" * 101)
        with self.assertRaisesRegex(ValueError, "100 candidate"):
            candidate_rules(document)
        reader = MagicMock()
        reader.is_encrypted = False
        reader.pages = [MagicMock()] * 101
        with patch("pypdf.PdfReader", return_value=reader), self.assertRaisesRegex(ValueError, "100 pages"):
            extract_document("long.pdf", b"fake PDF")

    def test_adapter_is_injected_and_never_autoconfirms(self):
        supplied = {"id": "a", "text": "a", "status": "confirmed", "source": {"quote": "a"}}
        result = candidate_rules({"name": "manual", "segments": []}, extractor=lambda document: [supplied])
        self.assertEqual(result[0]["status"], "draft")
        self.assertEqual(supplied["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
