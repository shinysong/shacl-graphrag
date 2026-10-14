import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_business_questions_gleif import convert_rr


class AdapterTests(unittest.TestCase):
    def record(self):
        return {
            "Relationship.StartNode.NodeID": "a",
            "Relationship.EndNode.NodeID": "b",
            "Relationship.StartNode.NodeIDType": "LEI",
            "Relationship.EndNode.NodeIDType": "LEI",
            "Relationship.RelationshipType": "IS_FUND-MANAGED_BY",
            "Relationship.RelationshipStatus": "ACTIVE",
            "Registration.RegistrationStatus": "LAPSED",
            "Relationship.Period.1.periodType": "ACCOUNTING_PERIOD",
            "Relationship.Period.1.startDate": "2000-01-01",
            "Relationship.Period.2.periodType": "RELATIONSHIP_PERIOD",
            "Relationship.Period.2.startDate": "2020-01-01",
        }

    def test_distinct_period_role_status(self):
        r = convert_rr(self.record(), "r")
        self.assertEqual(len(r), 1)
        self.assertEqual(
            (r[0]["start"], r[0]["end"], r[0]["relation"], r[0]["registration_status"]),
            ("2020-01-01", "9999-12-31", "FUND_MANAGER", "LAPSED"),
        )

    def test_missing_period_not_inferred_from_accounting(self):
        r = self.record()
        del r["Relationship.Period.2.periodType"]
        self.assertEqual(convert_rr(r, "r")[0]["start"], "9999-12-31")

    def test_identifier_namespace_required(self):
        r = self.record()
        r["Relationship.EndNode.NodeIDType"] = "OTHER"
        with self.assertRaises(ValueError):
            convert_rr(r, "r")
