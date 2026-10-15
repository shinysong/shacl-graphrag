import json
import unittest
from unittest.mock import patch

from scripts import ontology_tools as tools

PREFIX = "@prefix bq: <urn:business-questions:> .\n"
DATA = (
    PREFIX
    + 'bq:r1 a bq:relationship; bq:id "r1"; bq:relation "direct"; bq:object "P1" .'
)
QUERY_PREFIX = "PREFIX bq: <urn:business-questions:> "
SHAPES = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix bq: <urn:business-questions:> .
bq:S a sh:NodeShape; sh:targetClass bq:relationship;
sh:property [sh:path bq:object; sh:minCount 1] ."""


class OntologyToolsTests(unittest.TestCase):
    def test_select_ask_and_provenance(self):
        result = tools.execute_query(
            DATA, QUERY_PREFIX + "SELECT ?r ?id WHERE {?r bq:id ?id}"
        )
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["source_ids"], ["r1"])
        self.assertEqual(result["rows"][0]["id"], "r1")
        self.assertEqual(result["completeness"], "unknown")
        self.assertTrue(tools.execute_query(DATA, "ASK {?s ?p ?o}")["boolean"])
        json.dumps(result)

    def test_row_limit_and_explicit_limit_caveat(self):
        data = PREFIX + "\n".join(f'bq:r{i} bq:id "{i}" .' for i in range(105))
        result = tools.execute_query(data, "SELECT * WHERE {?s ?p ?o}")
        self.assertEqual(len(result["rows"]), 100)
        self.assertTrue(result["truncated"])
        result = tools.execute_query(data, "SELECT * WHERE {?s ?p ?o} LIMIT 2")
        self.assertEqual(len(result["rows"]), 2)
        self.assertTrue(result["explicit_limit"])
        self.assertFalse(result["truncated"])
        self.assertEqual(result["completeness"], "unknown")

    def test_external_and_write_queries_rejected(self):
        for query in [
            "SELECT * WHERE {SERVICE <https://example.com> {?s ?p ?o}}",
            "SELECT * FROM <file:///etc/passwd> WHERE {?s ?p ?o}",
            "INSERT DATA {<urn:a> <urn:b> <urn:c>}",
            "CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}",
            'SELECT (<https://example.com/custom>("x") AS ?x) WHERE {}',
        ]:
            with self.subTest(query=query):
                self.assertEqual(tools.execute_query(DATA, query)["status"], "error")

    def test_paths_are_unknown_to_semantic_check(self):
        result = tools.check_query_contract(
            QUERY_PREFIX + "SELECT * WHERE {?s bq:relation+ ?o}", {}, {}
        )
        self.assertEqual(result["status"], "unknown", result)

    def test_contract_same_subject_and_wrong_model_intent(self):
        ontology = {
            "roles": {
                "direct": {
                    "required_constants": {
                        tools.NS + "relation": "direct",
                        tools.NS + "kind": "relationship",
                    }
                }
            }
        }
        query = (
            QUERY_PREFIX
            + 'SELECT * WHERE {?r bq:relation "direct"; bq:kind "relationship"}'
        )
        result = tools.check_query_contract(query, {"role": "direct"}, ontology)
        self.assertEqual(result["status"], "pass", result)
        # A matching declaration can pass even if a separate user's intent differs.
        self.assertIn("Model interpretation may be wrong", result["limitations"][0])
        mismatched = query.replace('"direct"', '"fund_manager"')
        self.assertEqual(
            tools.check_query_contract(mismatched, {"role": "direct"}, ontology)[
                "status"
            ],
            "fail",
        )
        split = (
            QUERY_PREFIX
            + 'SELECT * WHERE {?r bq:relation "direct". ?other bq:kind "relationship"}'
        )
        self.assertEqual(
            tools.check_query_contract(split, {"role": "direct"}, ontology)["status"],
            "fail",
        )
        filtered = query[:-1] + " FILTER(?r != bq:excluded)}"
        self.assertEqual(
            tools.check_query_contract(filtered, {"role": "direct"}, ontology)[
                "status"
            ],
            "unknown",
        )

    def test_shacl_missing_property_and_coverage(self):
        result = tools.check_evidence(DATA, ["r1"], SHAPES)
        self.assertTrue(result["conforms"], result)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["coverage"], "unknown")
        bad = DATA.replace('; bq:object "P1"', "")
        result = tools.check_evidence(bad, ["r1"], SHAPES)
        self.assertFalse(result["conforms"], result)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["results"])
        missing = tools.check_evidence(DATA, ["absent"], SHAPES)
        self.assertEqual(missing["status"], "unknown")
        self.assertEqual(missing["missing_record_ids"], ["absent"])
        self.assertEqual(
            tools.check_evidence(DATA, ["r1"], PREFIX)["status"], "unknown"
        )

    def test_evidence_projection_does_not_validate_unselected_bad_record(self):
        data = DATA + '\nbq:r2 a bq:relationship; bq:id "r2" .'
        self.assertTrue(tools.check_evidence(data, ["r1"], SHAPES)["conforms"])
        self.assertFalse(tools.check_evidence(data, ["r1", "r2"], SHAPES)["conforms"])

    def test_executable_shapes_unknown(self):
        shapes = SHAPES + '\nbq:S sh:sparql [sh:select "SELECT * WHERE {?s ?p ?o}"] .'
        self.assertEqual(
            tools.check_evidence(DATA, ["r1"], shapes)["status"], "unknown"
        )

    def test_worker_deadline_reaps_child(self):
        # Real subprocess deadline, reduced only for this deterministic test.
        with patch.object(tools, "TIMEOUT_SECONDS", 0.001):
            result = tools.execute_query(DATA, "SELECT * WHERE {?s ?p ?o}")
        self.assertEqual(result["error_type"], "timeout")

    def test_adversarial_join_deadline(self):
        data = PREFIX + "\n".join(f'bq:r{i} bq:id "{i}" .' for i in range(100))
        query = (
            "SELECT (COUNT(*) AS ?n) WHERE {?a ?b ?c . ?d ?e ?f . ?g ?h ?i . ?j ?k ?l}"
        )
        result = tools.execute_query(data, query)
        self.assertEqual(result["status"], "error", result)
        self.assertIn(
            result["error_type"], {"timeout", "worker_resource_or_process_failure"}
        )

    def test_output_cap_and_turtle_data_only(self):
        data = PREFIX + "\n".join(
            f'bq:r{i} bq:object "' + ("x" * 4000) + '" .' for i in range(40)
        )
        result = tools.execute_query(data, "SELECT * WHERE {?s ?p ?o}")
        self.assertEqual(result["error_type"], "output_limit")
        result = tools.execute_query("file:///etc/passwd", "ASK {}")
        self.assertEqual(result["status"], "error")

    def test_guard_uses_parse_tree_not_keyword_matching(self):
        result = tools.execute_query(
            DATA, 'SELECT ("SERVICE FROM INSERT" AS ?text) WHERE {}'
        )
        self.assertEqual(result["status"], "ok", result)

    def test_input_cap(self):
        result = tools.execute_query("x" * (tools.MAX_INPUT_BYTES + 1), "ASK {}")
        self.assertEqual(result["error_type"], "input_limit")


if __name__ == "__main__":
    unittest.main()
