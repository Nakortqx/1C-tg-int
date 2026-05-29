from brom import *
import ast
from retry import retry
import asyncio
from async_property import async_cached_property, AwaitLoader

import logging.config
import logging

from redis import asyncio as aioredis
def logging_config_soap():
    logging.config.dictConfig({
    'version': 1,
    'formatters': {
    'verbose': {
    'format': '%(name)s: %(message)s'
    }
    },
    'handlers': {
    'console': {
    'level': 'DEBUG',
    'class': 'logging.StreamHandler',
    'formatter': 'verbose',
    },
    },
    'loggers': {
    'zeep.transports': {
    'level': 'DEBUG',
    'propagate': True,
    'handlers': ['console'],
    },
    }
    })


async def get_requisites(client, catalog):
    meta_req = eval(f"client.Метаданные.Справочники.{catalog}.Реквизиты")
    req_list = ['Наименование']
    n = -1
    req_names = [x[0] for x in meta_req]
    while req_names[n] != 'Код':
        req_list.append(req_names[n])
        n -= 1
    req_list.append(req_names[n])


    have_groups = False
    if 'ЭтоГруппа' in req_names:
        have_groups = True

    meta_table = eval(f"client.Метаданные.Справочники.{catalog}.ТабличныеЧасти")
    meta_table = [x[0] for x in meta_table]

    req_list += meta_table
    
    return req_list, have_groups

async def get_table_reqs(table, client, catalog):
    meta_req = eval(f"client.Метаданные.Справочники.{catalog}.ТабличныеЧасти.{table}.Реквизиты")
    req_names = [x[0] for x in meta_req]
    
    return req_names[1:]

# @async_cached_property
# async def get_table_data(self):
#     meta_table = eval(f"client.Метаданные.Справочники.{catalog}.ТабличныеЧасти")
#     table_names = [x[0] for x in meta_table]

#     return table_names


async def get_values(client, catalog):
    # текЗапрос = client.СоздатьЗапрос()

    # текЗапрос.Текст = (f"""
    #     ВЫБРАТЬ
    #         {catalog}.Ссылка КАК Ссылка
    #     ИЗ
    #         Справочник.{catalog} КАК {catalog}
    #     """)
        
    # результат = текЗапрос.Выполнить()
    текСелектор = eval(f"client.Справочники.{catalog}.СоздатьСелектор()")

    #текСелектор.УстановитьКоллекцию("Справочник."+catalog)
    #текСелектор.АвтозагрузкаПолей = АвтозагрузкаПолейОбъектов.ВсеПоля()
    #req_list = await get_requisites()
    req_list, have_groups = await get_requisites(client, catalog)
    #table_names = get_table_data
    # both = req_list + table_names
    текСелектор.ДобавитьПоля(",".join(req_list))
    if have_groups:
        текСелектор.ДобавитьОтбор("ЭтоГруппа", False)
    текСелектор = текСелектор.ВыгрузитьРезультат()

    res = []
    req_list = [f"стр.Ссылка.{x}" for x in req_list]
    #table_names = [f"стр.Ссылка.{x}" for x in table_names]

    for стр in текСелектор:
        a = []
        for x in req_list:
            if isinstance(eval(x), ТабличнаяЧасть):
                ext = eval(x)
                last_dot = x.rfind(".")
                requsites = await get_table_reqs(x[last_dot+1:], client, catalog)
                b = [f"Табличная Часть {x[last_dot+1:]}, формат: {requsites}"]
                for req in requsites:
                    for value in ext:
                        try:
                            ext2 = eval(f"value.{req}")
                            if isinstance(ext2, ОбъектСсылка) and ext2.Пустая():
                                b.append("")
                            else: b.append(str(ext2))
                        except:
                            b.append("")
                    a.append(b)
            else:
                try:
                    ext = eval(x)
                    if isinstance(ext, ОбъектСсылка) and ext.Пустая():
                        a.append("")
                    else: a.append(str(ext))
                except:
                    a.append("")



        res.append(a)

    return res


def parse_data(data_str):
    try:
        data_str = re.sub(
            r'\b(Строка|Число|Дата|Булево|Перечисления\.\w+|Справочники\.\w+|Документы\.\w+)\b',
            r"'\1'",
            data_str
        )
        if not data_str.startswith('['):
            data_str = '[' + data_str + ']'
        return ast.literal_eval(data_str)
    except:
        return "ERROR: Ошибка заполнения команды."

def convert_value(data_type, value):
    # Существующие типы
    if data_type.startswith(('Справочники.', 'Документы.')):
        return f'{data_type}.НайтиПоКоду("{value}")' if value else ''
    elif data_type.startswith('Перечисления.'):
        return f'{data_type}.{value}' if value else ''
    elif data_type == 'Строка':
        return value
    elif data_type == 'Число':
        return int(value) if isinstance(value, (int, float)) else int(value)
    elif data_type == 'Дата':
        # Проверка формата даты (пример: 'YYYY-MM-DD')
        if not re.match(r'\d{4}-\d{2}-\d{2}', str(value)):
            return f"ERROR: Неверный формат даты: {value}"
        return f'Дата({value})'  # Или объект datetime, если нужно
    elif data_type == 'Булево':
        # Преобразование из строк 'Да'/'Нет' или 'True'/'False'
        if str(value).lower() in ('да', 'true', '1'):
            return True
        elif str(value).lower() in ('нет', 'false', '0'):
            return False
        else:
            return f"ERROR: Неверное булево значение: {value}"
    
    # Добавьте другие типы по аналогии
    else:
        return f"ERROR: Неизвестный тип данных: {data_type}"

def check_type(data_type, expected_type):
    if isinstance(expected_type, list):
        return data_type in expected_type
    else:
        return data_type == expected_type
    
# def valid_table(self, table):
#     if isinstance(table[0], str):


def serialize(types_config, data_str):
    data = parse_data(data_str)
    if isinstance(data, str) and data.startswith("ERROR"):
        return data
    result = {}
    for (type_info, data_element) in zip(types_config, data):
        type_kind, field_name, type_def = type_info[0], type_info[1], type_info[2]
        if type_kind == 'row':
            if len(data_element) != 2:
                return "ERROR: Неверное количество аргументов"
            data_type, value = data_element
            if not check_type(data_type, type_def):
                return f"ERROR: Type mismatch for {field_name}: expected {type_def}, got {data_type}"
            r = convert_value(data_type, value)
            if isinstance(r, str) and r.startswith("ERROR: "):
                return r
            result[field_name] = r
        elif type_kind == 'table':
            columns_def = type_def
            processed_table = []
            for raw_row in data_element:
                if len(columns_def) == 1 and len(raw_row) == 2 and not isinstance(raw_row[0], (list, tuple)):
                    row = [raw_row]
                else:
                    row = raw_row
                row_dict = {}
                for col_def, col_data in zip(columns_def, row):
                    col_name, expected_types = col_def[0], (col_def[1] if isinstance(col_def[1], list) else [col_def[1]])
                    col_type, col_value = col_data
                    if col_type not in expected_types:
                        return f"ERROR: Type mismatch in column {col_name}: expected {expected_types}, got {col_type}"
                    r1 = convert_value(col_type, col_value)
                    if isinstance(r1, str) and r1.startswith("ERROR: "):
                        return r1
                    row_dict[col_name] = r1
                processed_table.append(row_dict)
            result[field_name] = processed_table
    return result

async def get_types(redis, client, catalog):
    cat = to_num_string(catalog)
    types = await redis.get(f"types_catalog:catalog_{cat}")
    if not types:
        tryis = 0
        while tryis < 5:
            try:
                code = client.ВыполнитьКод(f"""
                    Результат = Новый Массив;
                    Мета = Метаданные.Справочники.{catalog};
                                        
                    Для каждого реквизит Из Мета.Реквизиты Цикл
                        Темп = Новый Массив;
                        ТемпН = Новый Массив;
                        Темп.Добавить("row");                 
                        Темп.Добавить(реквизит.Имя);
                        Для каждого тип Из реквизит.Тип.Типы() Цикл
                            Если Не тип = Тип("Строка") и Не тип = Тип("Число") и Не тип = Тип("Булево") и Не тип = Тип("Дата") Тогда
                                Ссылка = Новый (тип);
                                МД = Ссылка.Метаданные();
                        
                                Если Метаданные.Справочники.Содержит(МД) Тогда
                                    ТемпН.Добавить("Справочники."+МД.Имя); // ПОМЕНЯТЬ Справочник.Ссылка
                                ИначеЕсли Метаданные.Документы.Содержит(МД) Тогда
                                    ТемпН.Добавить("Документы."+МД.Имя);
                                ИначеЕсли Метаданные.Перечисления.Содержит(МД) Тогда
                                    ТемпН.Добавить("Перечисления."+МД.Имя);
                                КонецЕсли;
                                        
                        ИначеЕсли тип = Тип("Строка") Тогда
                            ТемпН.Добавить("Строка");
                        ИначеЕсли тип = Тип("Число") Тогда
                            ТемпН.Добавить("Число");  
                        ИначеЕсли тип = Тип("Булево") Тогда
                            ТемпН.Добавить("Булево");
                        ИначеЕсли тип = Тип("Дата") Тогда
                            ТемпН.Добавить("Дата");  
                        КонецЕсли;  
                                                        
                        КонецЦикла;
                                        
                    Если ТемпН.Количество() > 1 Тогда
                        Темп.Добавить(ТемпН);
                    Иначе
                        Темп.Добавить(ТемпН[0]);
                    КонецЕсли;
                                        
                    Результат.Добавить(Темп) 
                    КонецЦикла;
                                        
                Для Каждого ТабличнаяЧасть Из Мета.ТабличныеЧасти Цикл
                    ТемпТ = Новый Массив;
                    ТемпС = Новый Массив;
                    ТемпТ.Добавить("table");
                    ТемпТ.Добавить(ТабличнаяЧасть.Имя);                      
                    Для Каждого РеквизитТЧ Из ТабличнаяЧасть.Реквизиты Цикл
                        Темп = Новый Массив;
                        ТемпН = Новый Массив;
                        Темп.Добавить(РеквизитТЧ.Имя);
                        Для каждого тип Из РеквизитТЧ.Тип.Типы() Цикл
                            Если Не тип = Тип("Строка") и Не тип = Тип("Число") и Не тип = Тип("Булево") и Не тип = Тип("Дата") Тогда
                                Ссылка = Новый (тип);
                                МД = Ссылка.Метаданные();
                        
                                Если Метаданные.Справочники.Содержит(МД) Тогда
                                    ТемпН.Добавить("Справочники."+МД.Имя); 
                                ИначеЕсли Метаданные.Документы.Содержит(МД) Тогда
                                    ТемпН.Добавить("Документы."+МД.Имя);
                                ИначеЕсли Метаданные.Перечисления.Содержит(МД) Тогда
                                    ТемпН.Добавить("Перечисления."+МД.Имя);
                                КонецЕсли;
                                        
                            ИначеЕсли тип = Тип("Строка") Тогда
                                ТемпН.Добавить("Строка");
                            ИначеЕсли тип = Тип("Число") Тогда
                                ТемпН.Добавить("Число");  
                            ИначеЕсли тип = Тип("Булево") Тогда
                                ТемпН.Добавить("Булево");
                            ИначеЕсли тип = Тип("Дата") Тогда
                                ТемпН.Добавить("Дата");
                            КонецЕсли; 
                                                                            
                        КонецЦикла;
                    Если ТемпН.Количество() > 1 Тогда
                        Темп.Добавить(ТемпН);
                    Иначе
                        Темп.Добавить(ТемпН[0]);
                    КонецЕсли;
                    ТемпС.Добавить(Темп);

                    КонецЦикла;          
                                        
                    
                    ТемпТ.Добавить(ТемпС); 
                    //КонецЦикла;
                    
                Результат.Добавить(ТемпТ); 
                КонецЦикла;
                """)
            
                code.insert(0, ['row', 'Наименование', 'Строка'])
                await redis.set(f"types_catalog:catalog_{cat}", str(code))
                await redis.expire(f"types_catalog:catalog_{cat}", 3600)
                return str(code)
            except Exception as e:
                logging.error(e)
                tryis +=1
                await asyncio.sleep(5)
        return "Серверная ошибка. Повторите команду"
    else: return types

async def add_object(new_obj, key, value, client):
    if type(value) == str and any(value.startswith(pref) for pref in ["Справочники.", "Документы."]):
            if eval(f"client.{value}.Пустая()"):
                return f"ERROR: Объект для поля {key} не обнаружен."
            setattr(new_obj, key, eval(f"client.{value}"))
    elif type(value) == str and value.startswith("Перечисления."):
        if not eval(f"client.{value}"):
            return f"ERROR: Объект для поля {key} не обнаружен."
        setattr(new_obj, key, eval(f"client.{value}"))
    else: setattr(new_obj, key, value)
    return "success"

async def create_entry(ai_data, redis, client, catalog):
    try:
        types = await get_types(redis, client, catalog)
        types = ast.literal_eval(types)
    except:
        return "Серверная ошибка. Повторите команду"
    json_data = serialize(types, ai_data)
    if isinstance(json_data, str) and json_data.startswith("ERROR"):
        return "Неверный формат входных данных. " + json_data
    
    new_entry = eval(f"client.Справочники.{catalog}.СоздатьЭлемент()")
    for key in json_data.keys():
        if isinstance(json_data[key], list):
            for row in json_data[key]:
                str_table = eval(f"new_entry.{key}.Добавить()")
                for row_key in row.keys():
                    value = row[row_key]
                    res = await add_object(str_table, row_key, value, client)
                    if res != "success":
                        return res
        else:
            res = await add_object(new_entry, key, json_data[key], client)
            if res != "success":
                return res
    new_entry.Записать()

    return "success"


def generate_instruction(types_config):
    instruction = []
    examples = []
    
    # Шапка инструкции
    instruction.append(
        "**Инструкция для заполнения данных**\n\n"
        "Сформируйте строку в формате: `[тип, значение], [тип, значение], ...`\n"
        "Правила:\n"
        "- Значения должны строго соответствовать типам из структуры.\n"
        "- Для таблиц используйте вложенные списки `[[[тип, значение], ...], ...], слово `Таблица` НЕ использовать`.\n"
        "- Пустые значения указываются как `[тип, '']`.\n\n"
        "**Структура данных:**\n"
    )
    
    # Обработка каждого элемента конфигурации
    for idx, item in enumerate(types_config):
        item_type = item[0]
        field_name = item[1]
        type_def = item[2]
        
        if item_type == 'row':
            if isinstance(type_def, list):
                types = " | ".join(type_def)
                example_types = type_def[0]
            else:
                types = type_def
                example_types = type_def
            
            example_value = _generate_example_value(example_types, field_name)
            examples.append(f"[{example_types}, {example_value}]")
            
            instruction.append(
                f"{idx + 1}. **{field_name}**\n"
                f"   - Тип: `{types}`\n"
                f"   - Пример: `[{example_types}, {example_value}]`\n"
            )
        
        elif item_type == 'table':
            table_name = field_name
            columns = type_def
            table_examples = []
            
            instruction.append(f"{idx + 1}. **Таблица '{table_name}'**\n")
            
            for col in columns:
                col_name = col[0]
                col_types = col[1] if isinstance(col[1], list) else [col[1]]
                
                instruction.append(
                    f"   - Колонка **{col_name}**\n"
                    f"     - Допустимые типы: `{' | '.join(col_types)}`\n"
                )
                
                example_type = col_types[0]
                example_value = _generate_example_value(example_type, field_name)
                table_examples.append(f"[{example_type}, {example_value}]")
            
            # Пример строки таблицы
            example_row = f"[{', '.join(table_examples)}]"
            examples.append(f"[{example_row}]")  # Двойное вложение для таблиц
            instruction.append(f"   - Пример строки: `{example_row}`\n")
    
    # Формирование полного примера
    instruction.append("\n**Пример полных данных:**\n[" + ",".join(examples) + "]")
    
    instruction.append(
        "\n**Важно:**\n"
        "- НИКОГДА НЕ ОПЕРИРУЙТЕ ВЕЩЕСТВЕННЫМИ ДАННЫМИ ИЗ ПРИМЕРОВ\n"
        "- Заполняте все поля, которые вы можете заполнить\n"
        "- Сохраняйте порядок полей как в структуре.\n"
        "- Переносы строк не допускаются.\n"
        "- Для справочников указывайте код объекта (например, `'001'`). Код объекта можно узнать командой в соответствующем справочнике\n"
        "- Для перечислений указывайте название перечисления (например, `'Аренда'`)\n"
        "- Всегда проверяйте коды объектов справочников командой !GetCatalogInfo, если тип объекта это ссылка на справочник.\n"
        "- Всегда проверяйте названия перечислений командой !GetEnumValues, если тип объекта это ссылка на перечисление.\n"
        "- Даты в формате `YYYY-MM-DD`, булевы значения как `'Да'/'Нет'`.\n"
    )
    
    return "\n".join(instruction)

def _generate_example_value(data_type, field_name):
    """Генерирует пример значения для типа"""
    if data_type == "Строка":
        return f"'Пример_{field_name}'"
    elif data_type == "Число":
        return "123"
    elif data_type == "Дата":
        return "'2024-01-01'"
    elif data_type == "Булево":
        return "'Да'"
    elif data_type.startswith("Перечисления."):
        return "'название_перечисления'"
    elif any(data_type.startswith(pref) for pref in ["Справочники.", "Документы."]):
        return "'001'"
    else:
        return "'значение'"

def to_num_string(string):
    s = ''
    for i in string:
        s += str(ord(i))
    return s


async def get_catalogs(client, redis):
    retryis = 0

    catalogs = await redis.get("catalogs:all_catalogs")
    if not catalogs:
        while retryis < 5:
            try:
                meta = client.Метаданные.Справочники
                catalogs = [x[0] for x in meta]
                await redis.set("catalogs:all_catalogs", str(catalogs))
                await redis.expire("catalogs:all_catalogs", 3600)

                return f"Список справочников: {str(catalogs)}"
            except Exception as e:
                logging.error(e)
                retryis +=1
                await asyncio.sleep(5)
        return "ОШИБКА ПОЛУЧЕНИЯ ДАННЫХ ИЗ 1С.. ПОВТОРИТЕ КОМАНДУ"
    return f"Список справочников: {str(catalogs)}"


async def get_catalog_data(client, catalog, redis):
    retryis = 0
    cat = to_num_string(catalog)
    data = await redis.lrange(f"catalogs:catalog_{cat}", 0, -1)
    if not data:
        while retryis < 5:
            try:
                #data = CatalogData(client, catalog)
                requis = await get_requisites(client, catalog)
                requis = str(requis[0])
                values = str(await get_values(client, catalog))
                await redis.lpush(f"catalogs:catalog_{cat}", values, requis)
                await redis.expire(f"catalogs:catalog_{cat}", 3600)

                return f"Формат: {requis}. {values}"
            except Exception as e:
                logging.error(e)
                retryis +=1
                await asyncio.sleep(5)
        return "ОШИБКА ПОЛУЧЕНИЯ ДАННЫХ ИЗ 1С... ПОВТОРИТЕ КОМАНДУ"
    return f"Формат: {data[0]}. {data[1]}"


async def get_insert_info(client, catalog, redis):
    retryis = 0
    while retryis < 5:
        try:
            #data = AddToCatalog(client, catalog)
            types = await get_types(redis, client, catalog)
            data_for_ai = generate_instruction(ast.literal_eval(types))
            return data_for_ai
        except Exception as e:
            logging.error(e)
            retryis +=1
            await asyncio.sleep(5)
    return "ОШИБКА ПОЛУЧЕНИЯ ДАННЫХ ИЗ 1С... ПОВТОРИТЕ КОМАНДУ"


async def insert_catalog_data(client, catalog, params, redis):
    retryis = 0

    while retryis < 5:
        try: 
            #data = AddToCatalog(client, catalog)
            #data.ai_data = params
            result = await create_entry(params, redis, client, catalog)

            if result == 'success':
                key = f"catalogs:catalog_{to_num_string(catalog)}"
                if await redis.exists(key):
                    await redis.delete(key) 

            return result
        except Exception as e:
            logging.error(e)
            retryis += 1
            await asyncio.sleep(5)
    return "СЕРВЕРНАЯ ОШИБКА 1С... ПОВТОРИТЕ КОМАНДУ"

async def get_enums(client):
    v = client.Метаданные.Перечисления
    v = [b[0] for b in v]
    return  v

async def get_enum_values(client, pere, redis):
    retryis = 0
    pere_s = to_num_string(pere)
    values = await redis.lrange(f"peres:pere_{pere_s}", 0, -1)
    if not values:
        while retryis < 5:
            try:
                values = eval(f"client.Перечисления.{pere}.СоздатьСелектор().ВыгрузитьРезультат()")
                values = [v.Имя() for v in values]
                for v in values:
                    await redis.lpush(f"peres:pere_{pere_s}", v)
                return values
            except Exception as e:
                logging.error(e)
                retryis +=1
                await asyncio.sleep(5)
        return "СЕРВЕРНАЯ ОШИБКА 1С... ПОВТОРИТЕ КОМАНДУ"
    else: return values

async def printt():
        клиент = БромКлиент("http://localhost/test_for_vkr", "bromuser", "")
        клиент.Метаданные.Кеш = ФайловыйКешМетаданных("C:\\3kurs\\botai\\КешМетаданных")
        # data = await get_catalog_data(клиент, "Компьютеры")
        #data = await get_catalogs(клиент)
        #print(data)

        # новыйКонтр = клиент.Справочники.Клиенты.СоздатьЭлемент()
        # новыйКонтр.Наименование = "Сергей Сергеевич Сергеев"
        # новыйКонтр.ВидДисконтнойКарты = клиент.Справочники.ВидыДисконтныхКарт.Золотая
        # новыйКонтр.Записать()

        

        # data = await CatalogData(клиент, "Клиенты")
        # print(data.get_requisites)

        data = клиент.Метаданные.Справочники.Клиенты
        req_list = []
        req_names = [x[1].ПолноеИмя() for x in data]
        for n in range(len(req_names)):
            req_list.append(req_names[n])
        print(req_list)



        meta_req = eval(f"клиент.Метаданные.Справочники.Клиенты.ТабличныеЧасти")
        #req_list = ['Наименование']
        # n = -1
        req_names = [x[0] for x in meta_req]
        # while req_names[n] != 'Код':
        #     req_list.append(req_names[n])
        #     n -= 1
        
        print(req_names)

        # types = [
        #     ['row', 'Наименование', 'Строка'],
        #     ['row', 'СерийныйНомер', 'Строка'],
        #     ['row', 'Описание', 'Строка'],
        #     ['table', 'Комплектующие', [
        #         ['Комплектующая', [
        #             'Справочники.ОперативнаяПамять',
        #             'Справочники.Процессоры',
        #             'Справочники.Видеокарты',
        #             'Справочники.Мониторы'
        #         ]]
        #     ]]
        # ]





        # vv = AddToCatalog(клиент, "Компьютеры")

        # data_for_ai = format_for_ai(await vv.get_types)
        # ai_data   = "'ws-3-3','', '', [['ОперативнаяПамять', ['001']], ['Процессоры', ['001']], ['Видеокарты', ['']], ['Мониторы', ['001', '002']]]"

        # vv.ai_data = ai_data
        # result = await vv.create_entry()

        # print(data_for_ai)
        # print(result)


        #TODO
        #сторонний код..
        # pere = клиент.Метаданные.Перечисления

        # j = 0
        # for i in pere:
        #     print(i)
        #     j = i
            # for a in i[1]:
            #     print(a)
            #     for b in a[1]:
            #         #for c in b[1]:
            #             print(b)
        # kkl = клиент.Перечисления.ВидыНоменклатуры.СоздатьСелектор().ВыгрузитьРезультат()
        # kkl = [[k.Имя(), k] for k in kkl]
        # print(kkl)
        # values = ['Товар', 'Услуга', 'АрендаКомпьютера']
        # pere = "ВидыНоменклатуры"
        # values = [[v, eval(f"клиент.Перечисления.{pere}.{v}")] for v in values]
        # print(values)
        # v = клиент.Метаданные.Перечисления
        # v = [b[0] for b in v]
        # print(v)
        # for b in kkl:
        #     print(b)
        #print(kkl.Товар)
        # for k in kkl:
        #     print(k[1])
        #     for c in k[1]:
        #         print(c[1])
        #         for b in c[1]:
        #             print(b)
        #print(pere.ВидыНоменклатуры.Реквизиты.Ссылка.Товар)


        # pere = [i[1] for i in pere]
        # print(pere)

        # l = клиент.Справочники.ВидыДисконтныхКарт.НайтиПоКоду("000000003")
        # res = await insert_catalog_data(клиент, "Клиенты", '"Иванов Сидоров", "000000003"')
        # print(res)
        #клиент.Метаданные.Кеш.Очистить()
        # vv = AddToCatalog(клиент, "Посылки")

        # data = await vv.get_types
        # data_for_ai = generate_instruction(data) #Перечисления.ВидыНоменклатуры
        # vv.ai_data = "[Строка, 'post3'], [Перечисления.ВидыНоменклатуры, 'Товар'], [[[Справочники.Процессоры, '001'], [Справочники.Поставщики, '001'],[Число, 1]], [[Справочники.Мониторы, '001'], [Справочники.Поставщики, ''],[Число, 3]]], [[Справочники.Клиенты, '0007'], [Справочники.Клиенты, '0008']]"
        # # print(data)
        # # print(data_for_ai)
        # print(await vv.create_entry())
        # c = клиент.Справочники.ВидыДисконтныхКарт.НайтиПоКоду("000000002")
        # print(c.Пустая())
        # ai_data = '[Строка, "Онигири с сыром"], [Справочники.Компьютеры, ""], [Число, 95], [Перечисления.ВидыНоменклатуры, "Товар"]'
        # vv = AddToCatalog(клиент, "Номенклатура")
        # data = await vv.get_types
        # vv.ai_data = ai_data

        # value = "Перечисления.ВидыНоменклатуры.Товарs"
        # if not eval(f"клиент.{value}"):
        #     print("Пустая")
        # else:
        #     print(f"клиент.{value}")
        # print(data)
        # print(vv.serialize(data, ai_data))
        # print(await vv.create_entry())
        redis = await aioredis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
        #await get_catalog_data(клиент, "Клиенты", redis)
        #await insert_catalog_data(клиент, "Клиенты", '[Строка, "Лавров Михаил Александрович"]', redis)
        b = await get_insert_info(клиент, "Посылки", redis)
        print(b)
def asd():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(printt())
#asyncio.run(printt())
#asd()



# Выборка всех элементов справочника "Номенклатура" РАБОТАЕТ
# текСелектор = клиент.СоздатьСелектор()

# текСелектор.УстановитьКоллекцию("Справочник.Номенклатура")
# текСелектор.АвтозагрузкаПолей = АвтозагрузкаПолейОбъектов.ВсеПоля()
# req_list = ['Наименование','ВидНоменклатуры', 'Компьютер', 'Цена']
# req_list = [f"стр.{x}" for x in req_list]

# res = []
# результат = текСелектор.ВыгрузитьРезультат()
# for стр in результат:
#     for x in req_list:
#         try:
#             res.append(str(eval(x)))
#         except:
#             pass
# print(res)



# for текСсылка in текСелектор:
# 	print("Наименование: {0}; Код: {1}".format(текСсылка.Наименование, текСсылка.Код))



      
# promt = "Дан список с наименованием компютеров и их комплектующих. Напиши количество и названия компьютеров, у которых меньше 32гб оперативной памяти. "
# RES = promt + str(pc.get())

# текЗапрос = клиент.СоздатьЗапрос()
# текЗапрос.Текст = ("""
#     ВЫБРАТЬ
#         Компьютеры.*
#     ИЗ
#         Справочники.Компьютеры КАК Компьютеры
#  """)
# результат = текЗапрос.Выполнить()
# res = []
# for стр in результат:
#     res.append([стр.Ссылка.Наименование, стр.Ссылка.Описание])
# print(res)


# клиент.Метаданные.Кеш = ФайловыйКешМетаданных("C:\\3kurs\\botai\\КешМетаданных")
#pc = клиент.Метаданные.Найти("Справочники.Компьютеры.Реквизиты")
# pc = клиент.Метаданные.Справочники.Компьютеры.Реквизиты
# res = []
# n = -1
# t = [x[0] for x in pc]
# while t[n] != 'Код':
#     res.append(t[n])
#     n -= 1
# print(res)


# текЗапрос = клиент.СоздатьЗапрос()

# текЗапрос.Текст = ("""
# 	ВЫБРАТЬ
# 		ВидыНоменклатуры.Ссылка КАК Ссылка
# 	ИЗ
# 		Перечисление.ВидыНоменклатуры КАК ВидыНоменклатуры			
# """)

# результат = текЗапрос.Выполнить()

# for стр in результат:
# 	print(стр.Ссылка)



#работает, но лучше выгрузить метаданные и взять из них(каким-то блять образом)
# код = клиент.ВыполнитьКод("""
#     Результат = Новый Массив;
#     Сп = Метаданные.Справочники.Компьютеры.Реквизиты;
# 	Для каждого с из Сп Цикл
# 		Результат.Добавить(с.Имя);	
# 	КонецЦикла;
# """)
# print(код)