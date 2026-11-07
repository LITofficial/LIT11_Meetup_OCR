import unittest
from analyzer_schemas import FIELD_LABELS, BASE_DESCRIPTIONS, TUNED_DESCRIPTIONS, make_analyzer_definition, analyzer_id
from demo_logic import analysis_steps, validate_inputs, comparison_rows

class SchemaTuningTests(unittest.TestCase):
    def test_every_field_can_be_tuned_without_changing_other_fields(self):
        original = make_analyzer_definition(True)["fieldSchema"]["fields"]
        baseline_id = analyzer_id(True)
        for field in FIELD_LABELS:
            with self.subTest(field=field):
                overrides = {field: "사용자가 수정한 추출 기준"}
                edited = make_analyzer_definition(True, descriptions_override=overrides)["fieldSchema"]["fields"]
                self.assertEqual(edited[field]["description"], overrides[field])
                self.assertNotEqual(baseline_id, analyzer_id(True, descriptions_override=overrides))
                for other in FIELD_LABELS:
                    if other != field:
                        self.assertEqual(original[other], edited[other])
        self.assertEqual(original, make_analyzer_definition(True)["fieldSchema"]["fields"])

    def test_analyzer_id_ignores_mapping_order_and_surrounding_whitespace(self):
        first = dict(TUNED_DESCRIPTIONS)
        second = {k: " " + v + " " for k,v in reversed(list(first.items()))}
        self.assertEqual(analyzer_id(True, descriptions_override=first), analyzer_id(True, descriptions_override=second))

    def test_invalid_descriptions_rejected_before_requests(self):
        for overrides in ({"unknown":"test"}, {"location":""}, {"location":" "*4}, {"location":5}, {"location":"x"*1001}):
            with self.assertRaises(ValueError):
                make_analyzer_definition(True, descriptions_override=overrides)

    def test_modes_have_independent_request_plans(self):
        self.assertEqual(analysis_steps("tuned"), ("tuned",))
        self.assertEqual(analysis_steps("ocr"), ("ocr",))
        self.assertEqual(analysis_steps("compare"), ("ocr","basic","tuned"))

    def test_all_files_validated_not_only_selected_preview(self):
        self.assertTrue(validate_inputs([("valid.png", b"ok"), ("empty.pdf", b"")], BASE_DESCRIPTIONS, "tuned"))
        self.assertTrue(validate_inputs([("large.pdf", b"x"*(10*1024*1024+1))], BASE_DESCRIPTIONS, "ocr"))
        self.assertTrue(validate_inputs([("file.png",b"a")]*6, BASE_DESCRIPTIONS, "ocr"))
        self.assertEqual(validate_inputs([("file.png",b"a")], {}, "ocr"), [])
        self.assertTrue(validate_inputs([("file.png",b"a")], {}, "tuned"))

    def test_diff_includes_removed_value_and_unchanged_values(self):
        before = {"location":"B102", "event_title":"LIT"}
        after = {"location":"", "event_title":"LIT"}
        rows = {r["필드"]:r for r in comparison_rows(before, after)}
        self.assertEqual(rows["장소"]["변경"], "변경됨")
        self.assertEqual(rows["행사명"]["변경"], "동일")
        self.assertEqual(before["location"], "B102")

if __name__ == "__main__":
    unittest.main()
