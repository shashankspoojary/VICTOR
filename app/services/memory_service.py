# app/services/memory_service.py
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
        
        if all_chunks:
            self.vector_store.add_texts(all_chunks)

    def retrieve_context(self, query: str) -> str:
        """Gets semantic context formatted for AI consumption, with explicit profile override heuristics."""
        # Standard vector semantic search pass
        results = self.vector_store.search(query, top_k=3) or []
        
        # HEURISTIC PATHWAY: Intercept identity-seeking requests to prevent safety guardrail false-positives
        lowered_query = query.lower()
        identity_keywords = ["about me", "who am i", "my name", "know me", "tell me about me", "myself"]
        
        profile_context = ""
        if any(keyword in lowered_query for keyword in identity_keywords):
            userdata_path = LEARNING_DATA_DIR / "userdata.txt"
            if userdata_path.exists():
                try:
                    with open(userdata_path, "r", encoding="utf-8") as f:
                        user_profile_data = f.read().strip()
                        if user_profile_data:
                            profile_context = (
                                f"\n--- CRITICAL USER PERSONAL PROFILE DATA ---\n"
                                f"{user_profile_data}\n"
                                f"--- END USER PERSONAL PROFILE DATA ---\n"
                            )
                except Exception:
                    pass

        if not results and not profile_context:
            return "No relevant memory found."
            
        semantic_context = "\n".join([f"- {res}" for res in results])
        return f"{profile_context}\n{semantic_context}".strip()