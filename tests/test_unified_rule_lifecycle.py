"""Unit and regression tests for the Unified Rule Lifecycle Experiment
(unified-rule-lifecycle-1).
"""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from scripts.unified_rule_lifecycle import (
    ROUND_ORDER,
    STANDARD_DICTIONARY,
    build_llm_prompt_modes,
    build_shacl_shapes_for_round,
    evaluate_arm_g_shacl,
    evaluate_arm_p_python,
    evaluate_arm_s_sqlite,
    extract_shacl_llm_report,
    generic_tables_to_rdf,
    make_valid_base_tables,
    run_stage_a_experiment,
    run_stage_b_experiment,
    run_stage_c_experiment,
    run_stage_d_llm_prompt_bridge,
    run_unified_experiment,
)


class UnifiedRuleLifecycleTests(unittest.TestCase):
    def test_standard_dictionary_structure(self) -> None:
        self.assertEqual(set(STANDARD_DICTIONARY), {"words", "domains", "terms"})
        self.assertIn("RATE_0_1", STANDARD_DICTIONARY["domains"])
        self.assertEqual(
            STANDARD_DICTIONARY["domains"]["RATE_0_1"]["null_policy"], "unknown"
        )
        self.assertIn(
            "gross_amount",
            STANDARD_DICTIONARY["terms"]["net_amount"]["disallowed_synonyms"],
        )

    def test_generic_rdf_mapper_is_rule_agnostic_and_complete(self) -> None:
        tables = make_valid_base_tables()
        g = generic_tables_to_rdf(tables)
        self.assertGreater(len(g), 25)

    def test_three_arms_agree_on_all_rounds_and_violation_modes(self) -> None:
        shapes = {r: build_shacl_shapes_for_round(r) for r in ROUND_ORDER}

        # 1. Valid base tables -> eligible in R0, R1, R2, R3
        valid_t = make_valid_base_tables()
        for r in ROUND_ORDER:
            p = evaluate_arm_p_python(valid_t, r)
            s = evaluate_arm_s_sqlite(valid_t, r)
            g = evaluate_arm_g_shacl(valid_t, r, shapes_graph=shapes[r])
            self.assertEqual(p, s)
            self.assertEqual(s, g)
            self.assertEqual(g["decision"], "eligible")

        # 2. R1 margin-floor violation: eligible in R0, blocked in R1/R2/R3
        margin_t = make_valid_base_tables(achieved_margin=0.12, min_margin=0.18)
        for r in ROUND_ORDER:
            p = evaluate_arm_p_python(margin_t, r)
            s = evaluate_arm_s_sqlite(margin_t, r)
            g = evaluate_arm_g_shacl(margin_t, r, shapes_graph=shapes[r])
            self.assertEqual(p, s)
            self.assertEqual(s, g)
            expected = "eligible" if r == "R0" else "blocked"
            self.assertEqual(g["decision"], expected)

        # 3. R2 dual-role cardinality violation: eligible in R0/R1, blocked in R2/R3
        role_t = make_valid_base_tables()
        role_t["approval_reviews"][1]["review_role"] = "Observer"
        for r in ROUND_ORDER:
            p = evaluate_arm_p_python(role_t, r)
            s = evaluate_arm_s_sqlite(role_t, r)
            g = evaluate_arm_g_shacl(role_t, r, shapes_graph=shapes[r])
            self.assertEqual(p, s)
            self.assertEqual(s, g)
            expected = "eligible" if r in ("R0", "R1") else "blocked"
            self.assertEqual(g["decision"], expected)

        # 4. R3 5-hop division conflict: eligible in R0/R1/R2, blocked in R3
        div_t = make_valid_base_tables(req_div="DIV_SALES", rev1_div="DIV_SALES")
        for r in ROUND_ORDER:
            p = evaluate_arm_p_python(div_t, r)
            s = evaluate_arm_s_sqlite(div_t, r)
            g = evaluate_arm_g_shacl(div_t, r, shapes_graph=shapes[r])
            self.assertEqual(p, s)
            self.assertEqual(s, g)
            expected = "blocked" if r == "R3" else "eligible"
            self.assertEqual(g["decision"], expected)

        # 5. Missing required attribute -> unknown across all three arms
        missing_t = copy.deepcopy(valid_t)
        missing_t["order_requests"][0]["net_amount"] = None
        for r in ROUND_ORDER:
            p = evaluate_arm_p_python(missing_t, r)
            s = evaluate_arm_s_sqlite(missing_t, r)
            g = evaluate_arm_g_shacl(missing_t, r, shapes_graph=shapes[r])
            self.assertEqual(p, s)
            self.assertEqual(s, g)
            self.assertEqual(g["decision"], "unknown")

    def test_unrelated_review_missing_reviewer_does_not_change_decision(self) -> None:
        tables = make_valid_base_tables()
        tables["approval_reviews"].append({
            "review_id": "UNRELATED", "request_id": "OTHER_REQUEST",
            "reviewer_id": "ABSENT", "decision": "Approve", "review_role": "Audit",
        })
        for round_id in ROUND_ORDER:
            expected = evaluate_arm_p_python(tables, round_id)
            self.assertEqual(expected["decision"], "eligible")
            self.assertEqual(evaluate_arm_s_sqlite(tables, round_id), expected)
            self.assertEqual(evaluate_arm_g_shacl(tables, round_id), expected)

    def test_existing_output_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp) / "summary.json"
            sentinel.write_text("original")
            with self.assertRaises(FileExistsError):
                run_unified_experiment(Path(tmp))
            self.assertEqual(sentinel.read_text(), "original")

    def test_stage_a_counterexample_gate_catches_l0_defects(self) -> None:
        res_a = run_stage_a_experiment()
        self.assertEqual(res_a["n_policies"], 24)
        self.assertEqual(res_a["n_witness_graphs"], 96)
        self.assertIsNone(res_a["L0_direct"]["svr"])
        self.assertEqual(res_a["L0_direct"]["naive_ser"], "24/24")
        self.assertEqual(res_a["L0_direct"]["cem"], "0/24")
        self.assertEqual(res_a["L1_workbench_dictionary_gate"]["cem"], "24/24")
        self.assertEqual(
            res_a["L1_workbench_dictionary_gate"]["cross_target_parity_psg"], "24/24"
        )

    def test_stage_b_and_stage_c_parity_and_invariance(self) -> None:
        res_b = run_stage_b_experiment(n_entities=6)
        self.assertEqual(res_b["psg_exact_agreement"], "36/36")
        self.assertEqual(res_b["gleif_transfer_24"]["status"], "not_executed")
        self.assertEqual(res_b["policies"]["S2_ArmG"]["wrong_approval"], 0)
        self.assertEqual(res_b["policies"]["S2_ArmG"]["unnecessary_abstention"], 0)
        self.assertGreater(res_b["policies"]["G1"]["unnecessary_abstention"], 0)

        res_c = run_stage_c_experiment(cases_per_round=12)
        self.assertEqual(res_c["overall_psg_parity"], "48/48")
        for diff_item in res_c["evolution_diffs"]["ArmG_SHACL"]:
            self.assertEqual(diff_item["join_core_modified_lines"], 0)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "new-run"
            full = run_unified_experiment(tmp_path)
            self.assertTrue((tmp_path / "summary.json").exists())
            self.assertTrue((tmp_path / "stage_d_sample_prompts.json").exists())
            self.assertEqual(full["paid_api_calls"], 0)

    def test_stage_d_llm_prompt_modes_and_shacl_provenance(self) -> None:
        conflict_t = make_valid_base_tables(req_div="DIV_SALES", rev1_div="DIV_SALES")
        rep = extract_shacl_llm_report(conflict_t, "R3")
        self.assertEqual(rep["decision"], "blocked")
        self.assertEqual(len(rep["shacl_validation_results"]), 1)
        r0 = rep["shacl_validation_results"][0]
        self.assertEqual(r0["focus_node"], "ex:departments/DEPT_REQ")
        self.assertIn("ex:parentDivision", r0["result_path"])
        self.assertEqual(r0["value_node"], "ex:divisions/DIV_SALES")

        prompts = build_llm_prompt_modes(conflict_t, round_id="R3")
        self.assertIn("<RAW_TABLES>", prompts["M0_raw_table_prompt"])
        self.assertIn("<FUNCTION_CHECK_RESULT>", prompts["M1_bare_function_prompt"])
        self.assertNotIn("ex:divisions/DIV_SALES", prompts["M1_bare_function_prompt"])
        self.assertIn("<SHACL_VALIDATION_REPORT>", prompts["M2_shacl_report_prompt"])
        self.assertIn("ex:divisions/DIV_SALES", prompts["M2_shacl_report_prompt"])

        res_d = run_stage_d_llm_prompt_bridge()
        self.assertEqual(
            res_d["prompt_slot_coverage"]["M2_shacl_report_prompt"]["focus_node"],
            "240/240",
        )
        self.assertIsNone(res_d["custom_provenance_code_lines_added_r0_to_r3"])
        self.assertEqual(res_d["prompt_slot_coverage"]["M2_shacl_report_prompt"]["value_node"], "180/240")
        self.assertEqual(res_d["llm_calls"], 0)


if __name__ == "__main__":
    unittest.main()
