from backend.services.index.embeddings import embedding_service
print("Embedding service loaded:", embedding_service.is_loaded())
vec = embedding_service.embed_texts(["test"])
print("Embedding dim:", len(vec[0]))