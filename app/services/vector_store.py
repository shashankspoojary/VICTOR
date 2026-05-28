import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL, FAISS_INDEX_PATH

class VectorStore:
    def __init__(self):
        # We load the embedding model synchronously at startup
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)
        self.dimension = self.encoder.get_sentence_embedding_dimension()
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []
        self._load_index()

    def _load_index(self):
        """Loads FAISS index from disk if it exists."""
        if FAISS_INDEX_PATH.exists():
            # For a robust system, we would also serialize the chunks.
            # In this V1, we will re-embed from memory_service on boot for safety,
            # but we define the capability to load.
            pass

    def add_texts(self, texts: list[str]):
        """Embeds and indexes text chunks."""
        if not texts:
            return
        embeddings = self.encoder.encode(texts)
        faiss.normalize_L2(embeddings)
        self.index.add(np.array(embeddings).astype("float32"))
        self.chunks.extend(texts)

    def search(self, query: str, top_k: int = 3) -> list[str]:
        """Retrieves semantic matches."""
        if self.index.ntotal == 0:
            return []
        
        query_vector = self.encoder.encode([query])
        faiss.normalize_L2(query_vector)
        
        distances, indices = self.index.search(np.array(query_vector).astype("float32"), top_k)
        
        results = []
        for idx in indices[0]:
            if 0 <= idx < len(self.chunks):
                results.append(self.chunks[idx])
        return results