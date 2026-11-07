import unittest
from demo_logic import file_options, history_options

class SelectionRegressionTests(unittest.TestCase):
    def test_reordering_files_does_not_change_selected_identity(self):
        files = [("one.png", b"one"), ("two.png", b"two")]
        original = file_options(files)
        selected = next(key for key, value in original.items() if value[0] == "two.png")
        reordered = file_options(list(reversed(files)))
        self.assertEqual(reordered[selected], ("two.png", b"two"))
        self.assertEqual(file_options(files[1:])[selected], ("two.png", b"two"))

    def test_same_name_different_content_is_not_the_same_selection(self):
        options = file_options([("poster.png", b"one"), ("poster.png", b"two")])
        self.assertEqual(len(options), 2)

    def test_ocr_record_remains_available_after_tuning_run(self):
        runs = [{"id":"first", "mode":"ocr"}, {"id":"second", "mode":"tuned"}]
        options = history_options(runs)
        self.assertEqual(list(options), ["second", "first"])
        self.assertEqual(options["first"]["mode"], "ocr")
        self.assertEqual(options["second"]["mode"], "tuned")
        self.assertEqual(runs[0]["id"], "first")

    def test_history_selection_survives_append_and_retention(self):
        runs = [{"id":str(i), "mode":"ocr" if i%2 else "tuned"} for i in range(10)]
        selected_id = "8"
        runs = (runs + [{"id":"10", "mode":"tuned"}])[-10:]
        options = history_options(runs)
        self.assertEqual(options[selected_id]["id"], selected_id)
        self.assertNotIn("0", options)
        self.assertEqual(next(iter(options)), "10")

if __name__ == "__main__":
    unittest.main()
