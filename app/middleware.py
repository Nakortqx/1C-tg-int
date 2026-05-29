from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from typing import Callable, Awaitable, Dict, Any

class RedisMiddleware(BaseMiddleware):
    def __init__(self, redis):
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data['redis'] = self.redis
        return await handler(event, data)
    
class ClientMiddleware(BaseMiddleware):
    def __init__(self, client):
        self.client = client

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[None]],
        event: Message,
        data: Dict[str, Any]
    ) -> None:
        data['client'] = self.client
        return await handler(event, data)
    
class MysqlMiddleware(BaseMiddleware):
    def __init__(self, mysql):
        self.mysql = mysql

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data['mysql'] = self.mysql
        return await handler(event, data)
    
    