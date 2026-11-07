import unittest
from ui_tables import table_html

class TableTextTests(unittest.TestCase):
    def test_long_dates_and_links_are_preserved(self):
        long_text = "2026. 11. 9.(월) ~ 12. 11.(금) " + "긴 설명 "*300
        url = "https://example.com/" + "a"*400
        html = table_html([{"필드":"신청 마감일", "이전":long_text, "현재":url, "변경":"변경됨"}])
        self.assertIn(long_text, html)
        self.assertIn(url, html)
        self.assertIn('scope="col"', html)
        self.assertIn('width:34%', html)

    def test_extracted_html_is_rendered_as_text(self):
        html = table_html([{"<script>":'<img src=x onerror="alert(1)">'}])
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)

    def test_empty_and_missing_values(self):
        self.assertEqual(table_html([]), "")
        html = table_html([{"필드":"장소"}, {"필드":"행사명", "결과":None}])
        self.assertNotIn("None", html)
        self.assertEqual(html.count("<td>"), 4)

if __name__ == "__main__":
    unittest.main()
