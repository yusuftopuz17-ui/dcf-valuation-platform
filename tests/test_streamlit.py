"""Streamlit startup smoke test."""

from pathlib import Path


def test_streamlit_starts_without_exception():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    assert not test.exception


def test_method_selection_and_ccv_setup_start_without_exception():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    select = next(button for button in test.button if button.label == "Yöntemi Seç")
    select.click().run()
    assert not test.exception
    assert any(button.label == "● Comparable Companies" for button in test.button)
