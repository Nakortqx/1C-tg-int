from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
from settings import QWEN_URL

load_dotenv()

client = AsyncOpenAI(
    base_url=QWEN_URL,
    api_key=os.getenv('QWEN_API')
)