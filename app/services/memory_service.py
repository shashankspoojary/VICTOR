import os
from config import LEARNING_DATA_DIR
from app.services.vector_store import VectorStore

class MemoryService:
    def __init__(self):
        self.vector_store = VectorStore()
        self._load_learning_data()

    def _chunk_text(self, text: str, chunk_size: int = 500) -> list[str]:
        """Simple text chunker."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunks.append(" ".join(words[i:i + chunk_size]))
        return chunks

    def _load_learning_data(self):
        """Loads all .txt files from the learning data directory."""
        all_chunks = []
        for filename in os.listdir(LEARNING_DATA_DIR):
            if filename.endswith(".txt"):
                filepath = LEARNING_DATA_DIR / filename
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    all_chunks.extend(self._chunk_text(content))
        
        self.vector_store.add_texts(all_chunks)

    def retrieve_context(self, query: str) -> str:
        """Gets semantic context formatted for AI consumption."""
        results = self.vector_store.search(query, top_k=3)
        if not results:
            return "No relevant memory found."
        return "\n".join([f"- {res}" for res in results])