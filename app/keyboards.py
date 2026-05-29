from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def button_ex(settings):
    default_buttons_text = {
        "SETTING_1C": "1C mode ❌",
        "SETTING_PROCESS": "Отображать размышления ❌"
    }

    if settings["SETTING_1C"]:
        default_buttons_text["SETTING_1C"] = "1C mode ✅"

    if settings["SETTING_PROCESS"]:
        default_buttons_text["SETTING_PROCESS"] = "Отображать размышления ✅"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text = default_buttons_text["SETTING_1C"], callback_data="onec_mode")],
        [InlineKeyboardButton(text = default_buttons_text["SETTING_PROCESS"], callback_data="process_mode")]
    ])
    return markup


# async def button_ex(settings):
#     # Определение всех настроек и их текстов (✅/❌)
#     buttons_config = {
#         "SETTING_1C": {
#             "text": "1C mode",
#             "callback": "onec_mode"
#         },
#         "SETTING_PROCESS": {
#             "text": "Отображать размышления",
#             "callback": "process_mode"
#         }
#         # Можно добавить больше настроек по аналогии
#     }
    
#     # Создаем кнопки динамически
#     buttons = []
#     for setting_key, config in buttons_config.items():
#         # Определяем статус (вкл/выкл) и соответствующий символ
#         status_symbol = "✅" if settings.get(setting_key, False) else "❌"
#         button_text = f"{config['text']} {status_symbol}"
        
#         # Создаем кнопку
#         buttons.append([
#             InlineKeyboardButton(
#                 text=button_text, 
#                 callback_data=config['callback']
#             )
#         ])
    
#     # Создаем разметку с кнопками
#     markup = InlineKeyboardMarkup(inline_keyboard=buttons)
#     return markup