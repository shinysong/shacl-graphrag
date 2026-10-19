import hashlib
import unittest
from pathlib import Path

from rdflib import XSD, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic

from scripts import yago_native_tools as tools

FIX = Path(__file__).resolve().parents[1] / "experiments/yago"
SUBJECT = "http://yago-knowledge.org/resource/Abu_Nuwas"
SC = Namespace("http://schema.org/")
SELECT = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"


class YagoNativeToolsTests(unittest.TestCase):
    def test_roundtrip_preserves_terms(self):
        source = (
            '<urn:s> <urn:uri> <urn:o>; <urn:label> "bonjour"@fr; '
            '<urn:date> "0762"^^<http://www.w3.org/2001/XMLSchema#gYear>; '
            '<urn:num> "007"^^<http://www.w3.org/2001/XMLSchema#integer> .'
        )
        result = tools.query(source, SELECT)
        self.assertEqual(result["status"], "ok", result)
        self.assertTrue(
            isomorphic(
                Graph().parse(data=source, format="turtle"),
                Graph().parse(data=result["evidence_turtle"], format="turtle"),
            )
        )
        self.assertIn('"bonjour"@fr', [r["o"] for r in result["rows"]])
        self.assertIn(
            '"007"^^<http://www.w3.org/2001/XMLSchema#integer>',
            [r["o"] for r in result["rows"]],
        )
        self.assertEqual(result["completeness"], "unknown")

    def test_wrong_predicate_empty_and_non_source_rejected(self):
        source = "<urn:s> <urn:p> <urn:o> ."
        result = tools.query(
            source, "SELECT ?s ?p ?o WHERE { ?s ?p ?o FILTER(?p=<urn:wrong>) }"
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["evidence_turtle"], "")
        invented = "SELECT ?s ?p ?o WHERE { VALUES (?s ?p ?o) { (<urn:s> <urn:p> <urn:invented>) } }"
        self.assertEqual(tools.query(source, invented)["status"], "error")

    def test_unsafe_and_unsupported_queries(self):
        queries = [
            "SELECT ?s ?p ?o WHERE { SERVICE <https://example.org/> {?s ?p ?o} }",
            "SELECT ?s ?p ?o FROM <file:///etc/passwd> WHERE {?s ?p ?o}",
            "SELECT ?s ?p ?o WHERE {?s ?p ?o FILTER(<urn:f>(?o))}",
            "CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}",
            "ASK {?s ?p ?o}",
            "SELECT ?s WHERE {?s ?p ?o}",
        ]
        for query in queries:
            with self.subTest(query=query):
                self.assertEqual(tools.query("", query)["status"], "error")

    def test_caps_and_explicit_limit(self):
        source = "\n".join(f"<urn:s{i}> <urn:p> <urn:o> ." for i in range(101))
        result = tools.query(source, SELECT)
        self.assertEqual(len(result["rows"]), 100)
        self.assertTrue(result["truncated"])
        limited = tools.query(source, SELECT + " LIMIT 1")
        self.assertTrue(limited["explicit_limit"])
        self.assertFalse(limited["truncated"])
        large = '<urn:s> <urn:p> "' + ("x" * 70000) + '" .'
        result = tools.query(large, SELECT)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["cap_reasons"], ["output_limit"])

    def test_original_shapes_failure_and_incomplete_evidence(self):
        paths = [FIX / name for name in ("data.ttl", "schema.ttl", "taxonomy.ttl")]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        source, shapes, taxonomy = [p.read_bytes() for p in paths]
        result = tools.validate_evidence(source, shapes, taxonomy, SUBJECT)
        self.assertEqual(result["status"], "pass", result)
        graph = Graph().parse(data=source, format="turtle")
        graph.set((URIRef(SUBJECT), SC.birthDate, Literal("0762", datatype=XSD.string)))
        failed = tools.validate_evidence(
            graph.serialize(format="turtle"), shapes, taxonomy, SUBJECT
        )
        self.assertEqual(failed["status"], "fail", failed)
        self.assertTrue(
            any("OrConstraintComponent" in issue[2] for issue in failed["issues"])
        )
        graph = Graph().parse(data=source, format="turtle")
        graph.remove((URIRef(SUBJECT), SC.birthPlace, None))
        partial = tools.validate_evidence(
            graph.serialize(format="turtle"), shapes, taxonomy, SUBJECT
        )
        self.assertEqual(partial["status"], "pass", partial)
        self.assertEqual(partial["completeness"], "unknown")
        for evidence, subject, reason in [
            ("", SUBJECT, "empty_evidence"),
            (source, "urn:absent", "absent_subject"),
            ("<urn:s> <urn:p> <urn:o> .", "urn:s", "no_applicable_subject_shape"),
        ]:
            result = tools.validate_evidence(evidence, shapes, taxonomy, subject)
            self.assertEqual(result["status"], "unknown", result)
            self.assertIsNone(result["conforms"])
            self.assertEqual(result["reason"], reason)
        self.assertEqual(
            before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        )

    def test_executable_shapes_rejected(self):
        shapes = '@prefix sh: <http://www.w3.org/ns/shacl#> . <urn:S> sh:sparql [sh:select "SELECT * WHERE {?s ?p ?o}"] .'
        result = tools.validate_evidence(
            "<urn:s> <urn:p> <urn:o> .", shapes, "", "urn:s"
        )
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "executable_shapes_unsupported")


if __name__ == "__main__":
    unittest.main()
