from settings import LONG_MEMORY_LIMIT, DEFAULT_OUTPUT_LENGUAGE, DEFAULT_OUTPUT_INSTRUCTIONS, MODEL
from app.embeddings import find_relevant_info, EXAMPLE_EMBEDDINGS
from app.profile import rules, commands, one_memory
from app.ai_client import client
import logging

#TODO
#разные конфиги генерации для разных моделей


async def neuro(messages, memory):
    response = await client.chat.completions.create(
        temperature=0,
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": f"{DEFAULT_OUTPUT_LENGUAGE} Your memory of this conversation: {memory}. The context of previous messages: {messages[:-1]}" #{DEFAULT_OUTPUT_INSTRUCTIONS}
            },
            {
                "role": "user",
                "content": f"{messages[-1]}"
            }
        ]
    )
    return response.choices[0].message.content

# async def neuro_image(image, messages):
#     response = await client.chat.completions.create(
#        model=MODEL,
#        messages=[
#         {
#            "role": "system",
#             "content": f"Describe the image in detail. The context of previous messages: {messages[:-1]}"
#         },

#         {
#            "role": "user",
#            "content": [{
#                    "type": "text",
#                     "text": "Describe the image in detail."},

#                    {"type": "image_url",
#                    "image_url": {
#                        "url": f"data:image/png;base64,{image}"}
#                        }]
#         }
#         ])

#     return response.choices[0].message.content

# #для изображений с подписями
# async def neuro_image_text(image,text,messages):
#     response = await client.chat.completions.create(
#        model=MODEL,
#        messages=[
#         {
#            "role": "system",
#             "content": f"You analyze the image and factor it into the user's query. The context of previous messages: {messages[-1]}"
#         },

#         {
#            "role": "user",
#            "content": [{
#                    "type": "text",
#                     "text": text},

#                    {"type": "image_url",
#                    "image_url": {
#                        "url": f"data:image/png;base64,{image}"}
#                        }]
#         }
#         ])

#     return response.choices[0].message.content

#max_tokens добавить
async def neuro_memory(messages, memory):
    response = await client.chat.completions.create(
        temperature=0.3,
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": f"Update your memory by summarizing the following conversation and your old memory in your next response. Prioritize preserving important facts, things you've learned, useful tips, and long term reminders. You're limited to {LONG_MEMORY_LIMIT} characters, so be extremely brief and minimize words. Compress useful information. Old memory: {memory}.The context of previous messages: {messages}"
            },
        ]
    
    )
    return response.choices[0].message.content

async def neuro_onec(original_request, messages, memory, exampl):
    response = await client.chat.completions.create(
        temperature=0,
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": f"{rules}. Commands: {commands}. EXAMPLES: {exampl}. Your memory of this conversation: {memory}. The context of previous messages: {messages}. Original user question: {original_request}" #{DEFAULT_OUTPUT_INSTRUCTIONS}
            }
        ]
    )
    return response.choices[0].message.content

async def neuro_onec_first(messages, memory):
    exampl = await find_relevant_info(messages[-1], EXAMPLE_EMBEDDINGS)
    exampl_print = [x[0] for x in exampl]
    exampl = [x[1] for x in exampl]
    response = await client.chat.completions.create(
        temperature=0,
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": f"{rules}. Commands: {commands}. EXAMPLES FOR THIS PROBLEM: {exampl}. Your memory of this conversation: {memory}. The context of previous messages: {messages[:-1]}" #{DEFAULT_OUTPUT_INSTRUCTIONS}
            },
            {
                "role": "user",
                "content": f"{messages[-1]}"
            }
        ]
    )
    return response.choices[0].message.content, exampl, exampl_print

async def neuro_memory_1c(messages, memory):
    response = await client.chat.completions.create(
        temperature=0.3,
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": f"{one_memory}. Old memory: {memory}.The context of previous messages: {messages}"
            },
        ]
    
    )
    return response.choices[0].message.content