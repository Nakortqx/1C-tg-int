from app.generators import neuro_memory, neuro_onec, neuro_memory_1c
from app.onec import get_catalogs, get_catalog_data, get_insert_info, insert_catalog_data, get_enums, get_enum_values

from settings import LONG_MEMORY_LIMIT, MEMORY_MSG_LIMIT, SUMMORIZED_AFTER_ONEC, MAX_TG_MSG_LENGTH
import base64
import aiofiles
import re
import asyncio

def split_string(s, max_length):
    """Сплит сообщений на сообщения max_length, не разбивая слова и маркировку"""
    def find_last_newline(s, max_length):
        return max(s.rfind('\n', 0, max_length), s.rfind('\r\n', 0, max_length))

    def find_last_space(s, max_length):
        return s.rfind(' ', 0, max_length)

    def handle_triple_quotes(part):
        if part.count('```') % 2 != 0:
            return part + '\n```', True
        return part, False

    parts = []
    while len(s) > max_length:
        split_index = find_last_newline(s, max_length)
        if split_index != -1:
            part = s[:split_index].rstrip()
            s = s[split_index:].lstrip()
        else:
            split_index = find_last_space(s, max_length)
            if split_index != -1:
                part = s[:split_index].rstrip()
                s = s[split_index:].lstrip()
            else:
                part = s[:max_length]
                s = s[max_length:]

        quotes = handle_triple_quotes(part)
        part = quotes[0]
        if quotes[1]:
            s = '```\n' + s
        parts.append(part)

    parts.append(handle_triple_quotes(s)[0])
    return parts


async def get_1c_response(process_flag, original_request, response, context_memory, summorized_memory, user_id, redis, client, message, exampl):
    """
    Обработка запросов к 1C с поддержкой специальных команд.
    
    Args:
        process_flag: Флаг для отображения системных сообщений пользователю
        original_request: Исходный запрос пользователя
        response: Текущий ответ системы
        context_memory: Контекст диалога
        summorized_memory: Суммаризированный контекст
        user_id: ID пользователя
        redis: Клиент Redis
        client: Клиент 1C
        message: Объект сообщения для ответа пользователю
    
    Returns:
        str: Финальный ответ системы
    """

    async def handle_show_process(message, response):
        if len(response) > MAX_TG_MSG_LENGTH:
            splited_response = split_string(response, MAX_TG_MSG_LENGTH)
            for msg in splited_response:
                await message.answer(msg, parse_mode=None)
        else:
            await message.answer(response, parse_mode=None)

    async def handle_stop(match, **kwargs):
        """
        Обработчик команды !Stop()
        Прерывает цикл
        """
        indexb = kwargs['response'].rfind("!Stop()")
        indexf = kwargs['response'].find("!Stop()")
        res = kwargs['response'][:indexb] + kwargs['response'][indexf+7:]
        if not res:
            return "Done", True
        else: return res, True

    #TODO
    #ТРАИ В КОММЕНТАХ РЕАЛИЗОВАТЬ
    async def handle_get_catalogs(match, **kwargs):
        """Обработчик команды !GetCatalogs"""
        #try:
        onec_response = await get_catalogs(kwargs['client'], kwargs['redis'])
        await update("system", onec_response, kwargs['user_id'], kwargs['redis'])
        if kwargs['process_flag']:
            await handle_show_process(kwargs['message'], f"СИСТЕМА: {onec_response}")
        return kwargs['response'], False
        # except Exception as e:
        #     return await handle_error(str(e), **kwargs)
    
    async def handle_get_enums(match, **kwargs):
        """Обработчик команды !GetEnums"""
        onec_response = await get_enums(kwargs['client'])
        await update("system", onec_response, kwargs['user_id'], kwargs['redis'])
        if kwargs['process_flag']:
            await handle_show_process(kwargs['message'], f"СИСТЕМА: {onec_response}")
        return kwargs['response'], False
    
    async def handle_get_enum_values(match, **kwargs):
        """Обработчик команды !GetEnumValues"""
        enum_name = match.group(1)
        enums = await get_enums(kwargs['client'])
        if enum_name in enums:
            onec_response = await get_enum_values(kwargs['client'], enum_name, kwargs['redis'])
            await update("system", f"Перечисление: {enum_name}. {onec_response}", kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {onec_response}")
        else:
            error_msg = "Такого перечисления не существует. Анализируй список перечислений тщательнее."
            await update("system", error_msg, kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {error_msg}")
        return kwargs['response'], False

    async def handle_get_catalog_data(match, **kwargs):
        """Обработчик команды !GetCatalogData"""
        catalog_name = match.group(1)
        #try:
        catalogs = await get_catalogs(kwargs['client'], kwargs['redis'])
        if catalog_name in catalogs:
            onec_response = await get_catalog_data(kwargs['client'], catalog_name, kwargs['redis'])
            await update("system", f"Справочник: {catalog_name}. {onec_response}", kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {onec_response}")
        else:
            error_msg = "Такого справочника не существует. Анализируй список справочников тщательнее."
            await update("system", error_msg, kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {error_msg}")
        return kwargs['response'], False
        # except Exception as e:
        #     return await handle_error(str(e), **kwargs)
    
    async def handle_get_insert_catalog_info(match, **kwargs):
        catalog_name = match.group(1)

        catalogs = await get_catalogs(kwargs['client'], kwargs['redis'])
        if catalog_name in catalogs:
            onec_response = await get_insert_info(kwargs['client'], catalog_name, kwargs['redis'])
            await update("system", f"Информация для вставки в справочник {catalog_name}: {onec_response}", kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {onec_response}")
        else:
            error_msg = "Такого справочника не существует. Анализируй список справочников тщательнее."
            await update("system", error_msg, kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {error_msg}")
        return kwargs['response'], False
    
    async def handle_insert_catalog_data(match, **kwargs):
        args = match.group(1)
        category_pattern = r'^\s*"([^"]+)"\s*,\s*(.*)'
        split = re.search(category_pattern, args)
        
        if not split:
            error_msg = "Некорректное использование команды."
            await update("system", error_msg, kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {error_msg}")
            return kwargs['response'], False
        
        catalog_name = split.group(1)
        params = split.group(2)

        catalogs = await get_catalogs(kwargs['client'], kwargs['redis'])

        if catalog_name in catalogs:
            onec_response = await insert_catalog_data(kwargs['client'], catalog_name, params, kwargs['redis'])
            await update("system", onec_response, kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {onec_response}")
        else:
            error_msg = "Такого справочника не существует. Анализируй список справочников тщательнее."
            await update("system", error_msg, kwargs['user_id'], kwargs['redis'])
            if kwargs['process_flag']:
                await handle_show_process(kwargs['message'], f"СИСТЕМА: {error_msg}")
        return kwargs['response'], False    

    # Регистрация команд и их обработчиков
    COMMANDS = {
        r'!Stop\(\)': handle_stop,
        r'!GetCatalogs': handle_get_catalogs,
        r'!GetCatalogData\("([^"]+)"\)': handle_get_catalog_data,
        r'!GetInsertCatalogInfo\("([^"]+)"\)': handle_get_insert_catalog_info,
        r'!InsertCatalogData\s*\((.*?)\)': handle_insert_catalog_data,
        r'!GetEnums': handle_get_enums,
        r'!GetEnumValues\("([^"]+)"\)': handle_get_enum_values
    }

    async def process_command(response, **kwargs):
        """Обработка команд в текущем ответе."""
        for pattern, handler in COMMANDS.items():
            match = re.search(pattern, response)
            if match:
                response, should_exit = await handler(
                    match=match,
                    response=response,
                    **kwargs
                )
                return response, should_exit
        # error_msg = "Некорректное использование команды или команда не существует."
        # await update("system", error_msg, kwargs['user_id'], kwargs['redis'])
        # if kwargs['process_flag']:
        #     await kwargs['message'].answer("СИСТЕМА: " + error_msg, parse_mode=None)
        return response, False
    
    #TODO
    #обработка некорректных команд

    async def fetch_new_response(**kwargs):
        """Получение нового ответа от нейросети."""
        context_memory = await redis.lrange(f"context_memory:{kwargs['user_id']}", 0, -1)
        summorized_memory = await redis.get(f"summorized_memory:{kwargs['user_id']}")
        
        new_response = await neuro_onec(
            kwargs['original_request'],
            context_memory,
            summorized_memory,
            exampl
        )
        
        if '!Stop()' not in new_response and kwargs['process_flag']:
            await handle_show_process(kwargs['message'], new_response)
        
        await update("assistant", new_response, kwargs['user_id'], kwargs['redis'])
        
        message_count = await redis.get(f"message_count:{kwargs['user_id']}")
        message_count = int(message_count) if message_count else 0
        if message_count >= SUMMORIZED_AFTER_ONEC:
            await update_summorized_memory(kwargs['user_id'], kwargs['redis'], True)
        
        return new_response

    # Основной цикл обработки
    while True:
        # Обработка команд в текущем ответе
        response, should_exit = await process_command(
            response=response,
            client=client,
            user_id=user_id,
            redis=redis,
            process_flag=process_flag,
            message=message,
            exampl=exampl
        )
        if should_exit:
            return response

        # Если команд нет, получаем новый ответ
        response = await fetch_new_response(
            original_request=original_request,
            response=response,
            context_memory=context_memory,
            summorized_memory=summorized_memory,
            user_id=user_id,
            redis=redis,
            client=client,
            process_flag=process_flag,
            message=message,
            exampl=exampl
        )

        # Проверка наличия команд в новом ответе
        has_commands = any(re.search(pattern, response) for pattern in COMMANDS)
        if not has_commands:
            return response

        await asyncio.sleep(1)


async def image_to_base64(image_path):
    """Асинхронная конвертация изображения в base64"""
    async with aiofiles.open(image_path, "rb") as image_file:
        image_data = await image_file.read()
        return base64.b64encode(image_data).decode("utf-8")

async def clear_user_data(redis, user_id):
    pattern = f"*:{user_id}"
    cursor = '0'

    while cursor != 0:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern)

        if keys:
            await redis.delete(*keys)

async def clear_context(redis, user_id):
    keys_to_clear = [
        f"context_memory:{user_id}",
        f"summorized_memory:{user_id}",
        f"message_count:{user_id}"
    ]

    for key in keys_to_clear:
        if await redis.exists(key):
            await redis.delete(key)  

#Unused
async def check_user_exists(redis, user_id):
    pattern = f"*:{user_id}"
    cursor = '0'
    exists = False

    while cursor != 0 and not exists:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern)
        if keys:
            exists = True

    return exists

async def update(role, content, user_id, redis):
    if await redis.exists(f"context_memory:{user_id}"):
        context_memory = await redis.lrange(f"context_memory:{user_id}", 0, -1)
    else: context_memory = []
    context_memory = context_memory[-(MEMORY_MSG_LIMIT-1):] + ['{"role": '+ str(role)+', "content": ' + str(content)+'}']

    await redis.delete(f"context_memory:{user_id}")
    await redis.rpush(f"context_memory:{user_id}", *[msg for msg in context_memory])

    await redis.expire(f"context_memory:{user_id}", 3600)

    await redis.incr(f"message_count:{user_id}")

    await redis.expire(f"message_count:{user_id}", 3600)

async def update_summorized_memory(user_id, redis, onec):
    context_memory = await redis.lrange(f"context_memory:{user_id}", 0, -1)

    summorized_memory = await redis.get(f"summorized_memory:{user_id}")

    if onec:
        memory = await neuro_memory_1c(context_memory, summorized_memory)
    else: memory = await neuro_memory(context_memory, summorized_memory) 
    if len(memory) > LONG_MEMORY_LIMIT:
        memory = memory[LONG_MEMORY_LIMIT:] + f"[The limit of {LONG_MEMORY_LIMIT} characters has been exceeded. Compress the information better next time.]"

    await redis.set(f"summorized_memory:{user_id}", memory)

    await redis.expire(f"summorized_memory:{user_id}", 3600)

    await redis.set(f"message_count:{user_id}", 0)
