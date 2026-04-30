import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import paper_note_summarizer as pns


class PaperNoteSummarizerTests(unittest.TestCase):
    def test_schema_validation_and_evidence_rendering(self):
        summary = pns.sample_summary("测试论文")
        normalized = pns.validate_and_normalize(summary)

        self.assertEqual(normalized["paper_overview"]["title"]["value"], "测试论文")
        self.assertIn("page_refs", normalized["paper_content"]["main_idea"]["evidence"])

    def test_markdown_and_json_outputs(self):
        summary = pns.sample_summary("测试论文")
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            md_path = out / "note.md"
            evidence_path = out / "evidence.json"

            pns.render_markdown(summary, md_path)
            pns.write_evidence(summary, evidence_path)

            markdown = md_path.read_text(encoding="utf-8")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

            self.assertIn("# 论文笔记", markdown)
            self.assertIn("## 实验", markdown)
            self.assertIn("paper_overview", evidence)

    def test_chunk_pages_preserves_page_numbers(self):
        pages = [
            {"page_number": 1, "text": "a" * 20},
            {"page_number": 2, "text": "b" * 20},
            {"page_number": 3, "text": "c" * 20},
        ]
        chunks = pns.chunk_pages(pages, limit=60)
        flattened = [page["page_number"] for chunk in chunks for page in chunk]
        self.assertEqual(flattened, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
