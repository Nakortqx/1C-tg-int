import os
import asyncio
import logging
from dotenv import load_dotenv
from typing import AsyncGenerator
from urllib.parse import quote_plus

from redis import asyncio as aioredis
from brom import БромКлиент, ФайловыйКешМетаданных

from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram import Bot, Dispatcher
from aiogram.methods import DeleteWebhook

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.onec import logging_config_soap     
from app.handlers import router
from app.db_funcs import sync_loop, sync_to_db
from app.middleware import *
from app.tables import *
from app.embeddings import init_embeddings

#Везде траи сделать что бы при любой ошибке выдавался норм респонс
#Переводчик все таки нужен

load_dotenv()

DB_CONFIG = {
    "host": "localhost:3306",
    "user": "root",
    "password": quote_plus("Vfhbyf2013@"),
    "db": "bot1c_db",
}

logging.basicConfig(level=logging.INFO)


async def create_mysql_pool() -> AsyncGenerator[AsyncSession, None]:
    """Создание пула соединений с MySQL через SQLAlchemy."""
    DATABASE_URL = (
        f"mysql+aiomysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}/{DB_CONFIG['db']}"
    )
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        yield async_session
    finally:
        await engine.dispose()


async def connect_redis():
    """Подключение к Redis."""
    redis = await aioredis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
    try:
        await redis.ping()
        logging.info("Успешное подключение к Redis!")
        return redis
    except Exception as e:
        logging.critical(f"Ошибка подключения к Redis: {e}")
        raise


async def connect_1c():
    """Подключение к 1C."""
    try:
        client = БромКлиент("http://localhost/test_for_vkr", "bromuser", "")
        client.Ping()
        logging.info("Успешное подключение к 1C!")
        #TODO
        #папка для конкретной БД
        client.Метаданные.Кеш = ФайловыйКешМетаданных("C:\\3kurs\\botai\\КешМетаданных")
        return client
    except Exception as e:
        logging.critical(f"Ошибка подключения к 1C: {e}")
        raise


async def main():
    """Основная функция запуска бота."""
    shutdown_event = asyncio.Event()

    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    redis = await connect_redis()

    client = await connect_1c()

    await init_embeddings()

    async for mysql_pool in create_mysql_pool():
        dp.include_router(router)
        dp.message.middleware(RedisMiddleware(redis))
        dp.callback_query.middleware(RedisMiddleware(redis))
        dp.message.middleware(ClientMiddleware(client))
        dp.message.middleware(MysqlMiddleware(mysql_pool))
        dp.callback_query.middleware(MysqlMiddleware(mysql_pool))

        sync_task = asyncio.create_task(sync_loop(shutdown_event, redis, mysql_pool))

        await bot(DeleteWebhook(drop_pending_updates=True))

        try:
            await dp.start_polling(bot, skip_updates=True)

        finally:
            shutdown_event.set()
            sync_task.cancel()

            # Завершение работы
            await bot.session.close()
            logging.info("Bot stopped")

            logging.info("Ожидание завершения синхронизации...")
            if await redis.smembers("settings_update_queue"):
                await sync_to_db(redis, mysql_pool)

            await redis.aclose(close_connection_pool=True)
            logging.info("Redis connection closed")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt")
    finally:
        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        logging.info("Main loop stopped")
        loop.close()