"""Streamlit startup smoke test."""

from pathlib import Path


def test_streamlit_starts_without_exception():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    assert not test.exception
