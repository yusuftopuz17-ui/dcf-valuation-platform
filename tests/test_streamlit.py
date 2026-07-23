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


def test_public_ccv_run_button_explains_missing_confirmation():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    next(button for button in test.button if button.label == "Yöntemi Seç").click().run()
    next(button for button in test.button if button.label == "Halka Açık Şirketi Seç").click().run()
    run = next(button for button in test.button if button.label == "CCV Analizini Çalıştır")
    assert not run.disabled
    run.click().run()
    assert any("Hedef şirket henüz onaylanmadı" in error.value for error in test.error)
    assert not test.exception


def test_msft_example_prefills_public_setup():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    next(button for button in test.button if button.label == "Yöntemi Seç").click().run()
    next(button for button in test.button if button.label == "Halka Açık Şirketi Seç").click().run()
    next(button for button in test.button if button.label == "Microsoft (MSFT) örneğini doldur").click().run()
    assert next(item for item in test.text_input if item.label == "Şirket adı veya sembol").value == "MSFT"
    assert any("Microsoft Corporation (MSFT)" in success.value for success in test.success)
    assert not test.exception


def test_canva_example_prefills_private_setup_without_financial_fabrication():
    from streamlit.testing.v1 import AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    test = AppTest.from_file(str(app), default_timeout=20).run()
    next(button for button in test.button if button.label == "Yöntemi Seç").click().run()
    next(button for button in test.button if button.label == "Özel Şirketi Seç").click().run()
    next(button for button in test.button if button.label == "Canva özel şirket profil örneğini doldur").click().run()
    assert next(item for item in test.text_input if item.label == "Şirket adı").value == "Canva"
    assert next(item for item in test.text_input if item.label.startswith("Son yıllık hasılat")).value == ""
    assert any("parasal alanlar boş bırakıldı" in info.value for info in test.info)
    assert not test.exception
