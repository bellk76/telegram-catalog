from app.config import Settings
from app.keyboards import catalog_keyboard


def test_catalog_keyboard_opens_webapp(settings: Settings) -> None:
    keyboard = catalog_keyboard(settings.webapp_url)

    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Каталог"
    assert button.web_app is not None
    assert button.web_app.url == settings.webapp_url
