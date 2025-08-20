import os
from core.word_writer import WordWriter

def test_word_writer(tmp_path):
    docx = tmp_path / "out.docx"
    w = WordWriter(str(docx))
    w.append_steps(["Open app", "Click Login"])
    assert docx.exists()
