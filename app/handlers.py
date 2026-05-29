from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from dotenv import load_dotenv
from chatgpt_md_converter import telegram_format
from sqlalchemy.ext.asyncio import AsyncSession

from app.funcs import *
from app.db_funcs import *
from app.keyboards import button_ex
from app.generators import neuro, neuro_onec_first
from settings import SUMMORIZED_AFTER, MAX_TG_MSG_LENGTH

router = Router()
load_dotenv()

running_tasks = {}

class Generate(StatesGroup):
    text = State()
    photo_text = State()
    memory = State()

#Хэндлер settings
@router.message(Command("settings"))
async def cmd_settings(message: Message, redis, mysql: AsyncSession):
    user_id = message.from_user.id

    settings = await get_user_settings(user_id, redis, mysql)

    await message.answer(f'ID: {user_id}\n (переключение мода очищает контекст)',
                          reply_markup=await button_ex(settings))

#Хэндлер /del_cache
@router.message(Command("del_cache"))
async def cmd_del_cache(_, client):
    client.Метаданные.Кеш.Очистить()

# Хэндлер /stop_recursion
@router.message(Command('stop_recursion'))
async def cmd_stop_recursion(message: Message, state: FSMContext,):
    user_id = message.from_user.id
    task = running_tasks.get(user_id)
    if task is None:
        await message.answer("Нет запущенного self-promt'a")
    else:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        running_tasks.pop(user_id)
        await message.answer("self-promt остановлен.")
        await state.clear()

# Хэндлер /show_context
@router.message(Command("show_context"))
async def cmd_show_context(message: Message, redis):
    user_id = message.from_user.id
    if await redis.exists(f"context_memory:{user_id}"):
        context = await redis.lrange(f"context_memory:{user_id}", 0, -1)
        for i, msg in enumerate(context):
            m = f"Сообщение {i+1}.\n {msg}"
            if len(m) > MAX_TG_MSG_LENGTH:
                splited_response = split_string(m, MAX_TG_MSG_LENGTH)
                for msg in splited_response:
                    await message.answer(msg, parse_mode=None)
            else: await message.answer(m, parse_mode=None)
    else:
        await message.answer("Контекст пуст.")

# Хэндлер /show_memory
@router.message(Command("show_memory"))
async def cmd_show_memory(message: Message, redis):
    user_id = message.from_user.id
    if await redis.exists(f"summorized_memory:{user_id}"):
        memory = await redis.get(f"summorized_memory:{user_id}")
        await message.answer(memory)
    else:
        await message.answer("Память пуста.")


@router.message(Generate.text)
@router.callback_query(Generate.text)
async def generate_error(message: Message):
    error_text = "Подождите, бот все еще генерирует ответ..."
    await message.answer(error_text)

@router.message(Generate.memory)
@router.callback_query(Generate.memory)
async def generate_error(message: Message):
    error_text = "Подождите, бот обновляет память..."
    await message.answer(error_text)

# Хэндлер /start
@router.message(Command("start"))
async def cmd_start(message: Message):
    start_text = "Привет! Это бот, который может отвечать на вопросы. Напиши свой вопрос."
    await message.answer(start_text)

# Хэндлер /clear
@router.message(Command("clear"))
async def cmd_clear(message: Message, redis):
    user_id = message.from_user.id
    if await redis.exists(f"context_memory:{user_id}"):
        text = "Контекст очищен."
        await clear_context(redis, user_id)
    else:
        text = "Контекст пуст."

    await message.answer(text)

# Хэндлер 1С MODE
@router.callback_query(F.data == "onec_mode")
async def onec_mode(callback: CallbackQuery, redis, mysql: AsyncSession):
    user_id = callback.from_user.id

    settings = await get_user_settings(user_id, redis, mysql)
    settings["SETTING_1C"] = not settings["SETTING_1C"]

    await update_user_setting(user_id, "SETTING_1C", settings["SETTING_1C"], redis)
    await clear_context(redis, user_id)
    await callback.message.edit_reply_markup(reply_markup = await button_ex(settings))

# Хэндлер PROCESS
@router.callback_query(F.data == "process_mode")
async def process_mode(callback: CallbackQuery, redis, mysql: AsyncSession):
    user_id = callback.from_user.id

    settings = await get_user_settings(user_id, redis, mysql)
    settings["SETTING_PROCESS"] = not settings["SETTING_PROCESS"]

    await update_user_setting(user_id, "SETTING_PROCESS", settings["SETTING_PROCESS"], redis)
    await callback.message.edit_reply_markup(reply_markup = await button_ex(settings))

@router.message(F.text)
async def message_handler(message: Message, state: FSMContext, redis, client, mysql: AsyncSession):
    await state.set_state(Generate.text)

    user_id = message.from_user.id

    if not await redis.exists(f"context_memory:{user_id}"):
        await redis.set(f"message_count:{user_id}", 0)
        await redis.set(f"summorized_memory:{user_id}", "[Memory will be updated after 4 messages in the conversation]")

    data = await state.get_data()
    custom_text = data.get('custom_text', '')
    if not custom_text:
        text = message.text
    else: text = custom_text

    await update("user", text, user_id, redis)

    context_memory = await redis.lrange(f"context_memory:{user_id}", 0, -1)

    summorized_memory = await redis.get(f"summorized_memory:{user_id}")

    response_generating = await message.answer("Генерация ответа...")

    process = False
    if await check_setting(user_id, "SETTING_PROCESS", redis, mysql):
        process = True

    try:
        if await check_setting(user_id, "SETTING_1C", redis, mysql):
            response_pre, exampl, exampl_print = await neuro_onec_first(context_memory, summorized_memory)
            if process:
                await message.answer(f"Choosen examples:\n{exampl_print}")
                await message.answer(response_pre)
            await update("assistant", response_pre, user_id, redis)
            #chat_id = message.chat.id
            task = asyncio.create_task(get_1c_response(process, text, response_pre, context_memory, summorized_memory, user_id, redis, client, message, exampl))
            running_tasks[user_id] = task
            try:
                response = await task
                running_tasks.pop(user_id)
            except asyncio.CancelledError:
                return
        else: 
            response = await neuro(context_memory, summorized_memory)
            await update("assistant", response, user_id, redis)
    except:
        await message.answer("Ошибка при выполнении запроса...")
        await state.clear()
        return

    if len(response) > MAX_TG_MSG_LENGTH:
        splited_response = split_string(response, MAX_TG_MSG_LENGTH)
        for msg in splited_response:
            try:
                msg_formatted = telegram_format(msg)
                await message.answer(msg_formatted)
            except:
                await message.answer(msg, parse_mode=None)
    else:
        try:
            response_formatted = telegram_format(response)
            await message.answer(response_formatted)
        except:
            await message.answer(response, parse_mode=None)
    await response_generating.delete()

    await state.set_state(Generate.memory)
    
    message_count = await redis.get(f"message_count:{user_id}")
    message_count = int(message_count) if message_count else 0
    if message_count >= SUMMORIZED_AFTER:
        mem_update = await message.answer("Обновление памяти...")
        await update_summorized_memory(user_id, redis, False)
        await mem_update.delete()

    await state.clear()




######CИЛЬНО УСТАРЕЛО######

#Указать, что если модель не поддерживает обработку изображений, то она не будет это делать.
# @router.message(F.photo)
# async def message_photo_handler(message: Message, state: FSMContext, bot: Bot):
#     await state.set_state(Generate.photo_text)

#     user_id = message.from_user.id
#     if user_id not in user_ids:
#         user_ids.append(user_id)
#         context_memory[user_id] = []

#     image = message.photo[-1]
#     file_photo = await bot.get_file(image.file_id)
#     file_path = file_photo.file_path
#     file_url = f"https://api.telegram.org/file/bot{os.getenv('TELEGRAM_TOKEN')}/{file_path}"
 
#     file_name = f"{image.file_id}.jpg"
#     response = requests.get(file_url)
#     with open(file_name, "wb") as f:
#         f.write(response.content)

#     base64_image = image_to_base64(file_name)
#     if message.caption:
#         await update("user", message.caption, user_id)
#         response = await neuro_image_text(base64_image, message.caption, context_memory[user_id])
#     else: response = await neuro_image(base64_image, context_memory[user_id])
#     await message.answer(response) # , parse_mode="Markdown"

#     await update("assistant", response, user_id)
#     await state.clear()

#     os.remove(file_name)