import asyncio
import logging
from sqlalchemy.dialects.mysql import insert
from sqlalchemy import select, text
from app.tables import *

SYNC_INTERVAL = 10800
sync_lock = asyncio.Lock()

# 1 2 4 8 16 32 ..
SETTING_NAMES = {
    "SETTING_1C": 1,
    "SETTING_PROCESS": 2
}


async def get_user_settings(user_id, redis, mysql_pool):

    settings_bits = await redis.get(f"us:{user_id}")
    
    if settings_bits is not None:
        settings_bits = int(settings_bits)

    else:
        async with mysql_pool() as session:
            result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            user_settings = result.scalars().first()

            if user_settings:
                settings_bits = user_settings.settings
            else:
                settings_bits = 0
                new_user_settings = UserSettings(user_id=user_id, settings=settings_bits)
                session.add(new_user_settings)
                await session.commit()
        
        await redis.set(f"us:{user_id}", str(settings_bits))
        await redis.expire(f"us:{user_id}", 3600)
    
    result = {
        "SETTING_1C": bool(settings_bits & SETTING_NAMES["SETTING_1C"]),
        "SETTING_PROCESS": bool(settings_bits & SETTING_NAMES["SETTING_PROCESS"])
    }
    
    
    return result

async def check_setting(user_id, setting_name, redis, mysql_pool):
    if setting_name not in SETTING_NAMES:
        return False

    setting_flag = SETTING_NAMES[setting_name]
    
    settings_bits = await redis.get(f"us:{user_id}")
    
    if settings_bits is not None:
        return bool(int(settings_bits) & setting_flag)
    
    settings = await get_user_settings(user_id, redis, mysql_pool)
    return settings[setting_name]

    #if setting_flag == SETTING_1C:
    #    return settings[setting_name]
    
   # return False

async def update_user_setting(user_id, setting_name, value, redis):
    settings_bits = await redis.get(f"us:{user_id}")
    if settings_bits is not None:
        settings_bits = int(settings_bits)
    else:
        settings_bits = 0
    
    if setting_name in SETTING_NAMES:
        flag = SETTING_NAMES[setting_name]
    else:
        raise ValueError(f"Unknown setting: {setting_name}")
    
    # Обновляем биты
    if value:
        settings_bits |= flag  # Устанавливаем бит
    else:
        settings_bits &= ~flag  # Сбрасываем бит
    
    await redis.set(f"us:{user_id}", str(settings_bits))
    await redis.expire(f"us:{user_id}", 3600)
    
    await redis.sadd("settings_update_queue", user_id)
    return bool(settings_bits & SETTING_NAMES[setting_name])

async def sync_to_db(redis, mysql_pool):
    # Блокируем синхронизацию, чтобы избежать одновременных обновлений
    try:
        async with sync_lock:
                    users_to_update = []
                    
                    for _ in range(len(await redis.smembers("settings_update_queue"))):
                        user_id = await redis.spop("settings_update_queue")
                        if not user_id:
                            break
                        users_to_update.append(user_id)
                    
                    if not users_to_update:
                        return
                    
                    pipe = redis.pipeline()
                    for user_id in users_to_update:
                        pipe.get(f"us:{user_id}")
                    settings_values = await pipe.execute()
                    
                    updates = []
                    for i, user_id in enumerate(users_to_update):
                        if settings_values[i]:
                            updates.append((int(settings_values[i]), int(user_id)))
                    
                    if updates:
                        stmt = insert(UserSettings).values([
                            {"settings": settings, "user_id": user_id} for settings, user_id in updates
                        ])
                        d_stmt = stmt.on_duplicate_key_update(
                            settings = stmt.inserted.settings
                        )

                        async with mysql_pool() as session:
                            await session.execute(d_stmt)
                            await session.commit()

    except Exception as e:
        logging.error(f"Ошибка синхронизации с БД: {e}")
        await asyncio.sleep(1)

async def sync_loop(shutdown_event, redis, mysql):
    while not shutdown_event.is_set():
        try:
            if not await redis.smembers("settings_update_queue"):
                await asyncio.sleep(SYNC_INTERVAL)
                continue
            
            await sync_to_db(redis, mysql)
            
        except Exception as e:
            logging.error(f"Ошибка синхронизации с БД: {e}")
            await asyncio.sleep(1)