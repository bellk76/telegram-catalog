from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def catalog_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Каталог", web_app=WebAppInfo(url=webapp_url))],
        ],
    )
