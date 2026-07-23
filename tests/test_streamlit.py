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
    select = next(button for button in test.button if button.label == "Select Method")
    select.click().run()
    assert not test.exception
    assert any(button.label == "● Comparable Companies" for button in test.button)


def test_comparable_tool_opens_with_quick_analysis_controls():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    next(button for button in test.button if button.label == "Select Method").click().run()
    assert any(button.label == "Analyze" for button in test.button)
    assert any(item.label == "Ticker Symbol" for item in test.text_input)
    assert not test.exception


def test_comparable_tool_has_msft_default_without_preset_buttons():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    next(button for button in test.button if button.label == "Select Method").click().run()
    assert next(item for item in test.text_input if item.label == "Ticker Symbol").value == "MSFT"
    assert not any(button.label in {"AAPL", "MSFT", "GOOGL"} for button in test.button)
    assert not test.exception


def test_dcf_tool_opens_with_forward_and_reverse_modes():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    selects = [button for button in test.button if button.label == "Select Method"]
    selects[1].click().run()
    assert any(button.label == "Load Data" for button in test.button)
    mode = next(item for item in test.radio if item.label == "Analysis Mode")
    assert mode.options == ["Forward DCF — Fair Value", "Reverse DCF — Implied Growth"]
    assert not test.exception
