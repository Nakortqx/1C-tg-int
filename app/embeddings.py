from sklearn.metrics.pairwise import cosine_similarity
from app.profile import examples
from app.ai_client import client
from settings import EMBEDDING_MODEL
import logging

EXAMPLE_EMBEDDINGS = []

#TODO 
# эмбеддинги в файл, из файла при инициализации в оперативку
async def init_embeddings():
    global EXAMPLE_EMBEDDINGS
    logging.info("Генерация эмбеддингов...")
    exs = examples
    for us in exs:
        example = us[0]["content"]
        EXAMPLE_EMBEDDINGS.append([(example, str(us)), await create_embedding(example)])

async def create_embedding(text):
    input=[text]
    model=EMBEDDING_MODEL
    embedding = await client.embeddings.create(input=input, model=model)
    return embedding.data[0].embedding

async def find_relevant_info(query, embeddings_storage):

    #TODO переделать отдельно этот прикол
    #embeddings_storage = {x: await create_embedding(x) for x in embeddings_storage}

    query_embedding = await create_embedding(query)
    similarities = []
    
    for key, embedding in embeddings_storage:
        similarity = cosine_similarity([query_embedding], [embedding])[0][0]
        similarities.append((key, similarity))
    
    # Сортировка по релевантности
    similarities.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x  in similarities[:3]]
