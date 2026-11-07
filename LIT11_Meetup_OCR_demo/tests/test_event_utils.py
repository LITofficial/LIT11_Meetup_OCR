import unittest
from datetime import date

from analyzer_schemas import MODEL_NAMES, analyzer_id, make_analyzer_definition
from event_utils import (deadline_status, make_deadline_ics, make_ics, normalize_fields,
                         parse_event_time, parse_explicit_date, source_regions)


class AnalyzerSchemaTests(unittest.TestCase):
    def test_same_models_different_schema(self):
        basic = make_analyzer_definition(False)
        tuned = make_analyzer_definition(True, descriptions_override={"event_date": "실제 행사 참석 날짜만 추출한다."})
        self.assertEqual(basic["models"], MODEL_NAMES)
        self.assertEqual(tuned["models"], MODEL_NAMES)
        self.assertNotEqual(basic["fieldSchema"]["fields"], tuned["fieldSchema"]["fields"])
        self.assertEqual(analyzer_id(False), analyzer_id(True))
        self.assertNotEqual(analyzer_id(False), analyzer_id(True, descriptions_override={"event_date": "실제 행사 참석 날짜만 추출한다."}))
        self.assertEqual(analyzer_id(True), analyzer_id(True))


class EventUtilsTests(unittest.TestCase):
    def test_date_requires_explicit_year(self):
        self.assertIsNone(parse_explicit_date("11/11"))
        self.assertIsNone(parse_explicit_date("Feb 32, 2026"))
        self.assertEqual(str(parse_explicit_date("2026년 11월 11일")), "2026-11-11")
        self.assertEqual(str(parse_explicit_date("행사: 2026.11.11 (수)")), "2026-11-11")

    def test_deadline_and_alarm(self):
        today = date(2026, 11, 2)
        self.assertEqual(deadline_status("2026-11-02", today), ("오늘 마감", 0))
        self.assertEqual(deadline_status("2026-11-01", today), ("마감됨", -1))
        self.assertEqual(deadline_status("11/11", today), ("확인 필요", None))
        alarm = make_deadline_ics("밋업", "2026-11-11").decode("utf-8")
        self.assertIn("DTSTART:20261111T000000Z", alarm)
        self.assertIn("TRIGGER:-P1D", alarm)
        with self.assertRaises(ValueError):
            make_deadline_ics("밋업", "11/11")

    def test_source_regions(self):
        result = {"result": {"contents": [{"fields": {"event_title": {"source": "D(1,1,2,3,4,5,6,7,8);D(2,1,2,3,4)"}}}]}}
        regions = source_regions(result, "event_title")
        self.assertEqual(regions[0], (1, [(1, 2), (3, 4), (5, 6), (7, 8)]))
        self.assertEqual(regions[1], (2, [(1, 2), (4, 2), (4, 6), (1, 6)]))
        self.assertEqual(source_regions(result, "location"), [])

    def test_korean_am_pm(self):
        self.assertEqual(str(parse_event_time("오후 6시 30분")), "18:30:00")
        self.assertEqual(str(parse_event_time("오후 6:30")), "18:30:00")
        self.assertEqual(str(parse_event_time("오전 12시")), "00:00:00")
        self.assertEqual(str(parse_event_time("6:30 PM")), "18:30:00")
        self.assertEqual(str(parse_event_time("12 AM")), "00:00:00")
        self.assertEqual(str(parse_event_time("18시 30분")), "18:30:00")
        self.assertIsNone(parse_event_time("TBD"))

    def test_normalize_cu_fields(self):
        sample = {
            "result": {"contents": [{"fields": {
                "event_title": {"type": "string", "valueString": "LIT 밋업", "confidence": 0.92},
                "event_date": {"type": "date", "valueDate": "2026-11-11"},
            }}]}
        }
        values, confidence = normalize_fields(sample)
        self.assertEqual(values["event_title"], "LIT 밋업")
        self.assertEqual(values["event_date"], "2026-11-11")
        self.assertEqual(values["location"], "")
        self.assertEqual(confidence["event_title"], 0.92)

    def test_ics_is_utc_and_escapes_hangul(self):
        content = make_ics(
            title="LIT, AI; 밋업",
            date_text="2026-11-11",
            start_text="18:00",
            end_text="20:00",
            location="경북대 IT-5 B102",
        ).decode("utf-8")
        self.assertIn("DTSTART:20261111T090000Z", content)
        self.assertIn("DTEND:20261111T110000Z", content)
        self.assertIn("SUMMARY:LIT\\, AI\\; 밋업", content)
        self.assertIn("LOCATION:경북대 IT-5 B102", content)
        self.assertTrue(content.endswith("END:VCALENDAR\r\n"))

    def test_ics_does_not_guess_missing_year(self):
        with self.assertRaisesRegex(ValueError, "연도"):
            make_ics(title="LIT", date_text="11/11", start_text="18:00")

    def test_ics_line_folding_respects_octets(self):
        content = make_ics(
            title="한글" * 70, date_text="2026-11-11", start_text="18:00"
        ).decode("utf-8")
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in content.split("\r\n")))


if __name__ == "__main__":
    unittest.main()
