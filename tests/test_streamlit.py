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
    assert any(button.label == "● Benzer Şirketler" for button in test.button)


def test_comparable_tool_opens_with_quick_analysis_controls():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    next(button for button in test.button if button.label == "Yöntemi Seç").click().run()
    assert any(button.label == "Analiz Et" for button in test.button)
    assert any(item.label == "Borsa sembolü" for item in test.text_input)
    assert not test.exception


def test_msft_preset_is_available_in_comparable_tool():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    next(button for button in test.button if button.label == "Yöntemi Seç").click().run()
    assert next(item for item in test.text_input if item.label == "Borsa sembolü").value == "MSFT"
    assert any(button.label == "MSFT" for button in test.button)
    assert not test.exception


def test_dcf_tool_opens_with_forward_and_reverse_modes():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    selects = [button for button in test.button if button.label == "Yöntemi Seç"]
    selects[1].click().run()
    assert any(button.label == "Verileri Yükle" for button in test.button)
    mode = next(item for item in test.radio if item.label == "Analiz modu")
    assert mode.options == ["İleri DCF — Makul Değer", "Ters DCF — İma Edilen Büyüme"]
    assert not test.exception
