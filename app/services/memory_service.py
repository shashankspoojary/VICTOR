import os
import json
import logging
import threading
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

class MemoryService:
    _embeddings_cache = None
    _embeddings_lock = threading.Lock()

    @classmethod
    def _get_embeddings(cls):
        if cls._embeddings_cache is None:
            with cls._embeddings_lock:
                if cls._embeddings_cache is None:
                    cls._embeddings_cache = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        return cls._embeddings_cache

    def __init__(self, base_dir: str = "D:/VICTOR"):
        self.base_dir = Path(base_dir)
        self.learning_data_dir = self.base_dir / "database" / "learning_data"
        self.knowledge_lib_dir = self.base_dir / "knowledge_library"
        self.vector_store_dir = self.base_dir / "database" / "vector_store"
        self.memory_dir = self.base_dir / "database" / "memory"
        self.chats_data_dir = self.base_dir / "database" / "chats_data"

        # Ensure directories exist
        for d in [self.learning_data_dir, self.knowledge_lib_dir, self.vector_store_dir, self.memory_dir, self.chats_data_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Initialize embeddings lazily
        self.vector_store = None

    def preload_index(self):
        index_path = self.vector_store_dir / "index.faiss"
        if index_path.exists():
            try:
                self.vector_store = FAISS.load_local(
                    folder_path=str(self.vector_store_dir), 
                    embeddings=self._get_embeddings(),
                    allow_dangerous_deserialization=True
                )
                logger.info(f"Successfully pre-loaded FAISS index from {self.vector_store_dir}")
            except Exception as e:
                logger.warning(f"Failed to pre-load FAISS index on startup: {e}")
        else:
            logger.warning(f"FAISS index missing at {self.vector_store_dir}, skipping startup pre-load. Model is pre-warmed.")
            self._get_embeddings() # Ensure embeddings are pre-warmed

    def _get_all_documents(self) -> List[Document]:
        documents = []
        # Parse learning_data and knowledge_library
        for dir_path in [self.learning_data_dir, self.knowledge_lib_dir]:
            if not dir_path.exists():
                continue
            for file_path in dir_path.rglob("*.txt"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                        if text.strip():
                            # Add source metadata
                            documents.append(Document(page_content=text, metadata={"source": str(file_path)}))
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
        return documents

    def build_or_load_vector_store(self, force_rebuild: bool = False):
        index_path = self.vector_store_dir / "index.faiss"
        
        if index_path.exists() and not force_rebuild:
            print("Loading existing FAISS index...")
            self.vector_store = FAISS.load_local(
                folder_path=str(self.vector_store_dir), 
                embeddings=self._get_embeddings(),
                allow_dangerous_deserialization=True
            )
        else:
            print("Building new FAISS index...")
            docs = self._get_all_documents()
            if not docs:
                print("No documents found to index.")
                # Create an empty vector store if no docs
                self.vector_store = FAISS.from_texts(["Initial empty document."], self._get_embeddings())
            else:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=500,
                    chunk_overlap=50
                )
                chunks = text_splitter.split_documents(docs)
                self.vector_store = FAISS.from_documents(chunks, self._get_embeddings())
            
            self.vector_store.save_local(str(self.vector_store_dir))
            print(f"FAISS index saved to {self.vector_store_dir}")

    def get_relevant_context(self, query: str, k: int = 3) -> str:
        if not self.vector_store:
            self.build_or_load_vector_store()
            
        if not self.vector_store:
            return ""

        results = self.vector_store.similarity_search(query, k=k)
        
        context_blocks = []
        for i, doc in enumerate(results):
            source = doc.metadata.get("source", "Unknown")
            context_blocks.append(f"--- Context {i+1} (Source: {Path(source).name}) ---\n{doc.page_content}")
            
        return "\n\n".join(context_blocks)

    def get_user_profile(self) -> Dict[str, Any]:
        profile_path = self.memory_dir / "user_profile.json"
        if profile_path.exists():
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading user profile: {e}")
        return {}

    def update_user_profile(self, data: Dict[str, Any]) -> bool:
        profile_path = self.memory_dir / "user_profile.json"
        try:
            current_profile = self.get_user_profile()
            current_profile.update(data)
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(current_profile, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return False

    def save_chat_turn(self, session_token: str, user_message: str, assistant_message: str):
        timestamp = datetime.now().isoformat()
        log_path = self.chats_data_dir / f"{session_token}.txt"
        
        log_entry = f"[{timestamp}]\nUSER: {user_message}\nVICTOR: {assistant_message}\n\n"
        
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Error saving chat turn: {e}")


if __name__ == "__main__":
    print("Initializing MemoryService Testing Section...")
    memory_service = MemoryService()
    
    # 1. Test profile JSON read/write
    print("\n--- Testing User Profile JSON ---")
    memory_service.update_user_profile({"name": "Shashank", "role": "Owner", "theme": "dark"})
    profile = memory_service.get_user_profile()
    print(f"User Profile: {profile}")
    
    # 2. Test chat logging
    print("\n--- Testing Chat Logging ---")
    test_session = "test_session_001"
    memory_service.save_chat_turn(test_session, "Hello VICTOR!", "Greetings, Shashank. How can I assist you today?")
    print(f"Chat turn saved to {test_session}.txt")
    
    # 3. Test Vector Store building and retrieval
    print("\n--- Testing FAISS Vector Store ---")
    # Force rebuild to pick up the newly created text files
    memory_service.build_or_load_vector_store(force_rebuild=True)
    
    test_query = "What is VICTOR's personality?"
    print(f"\nQuery: '{test_query}'")
    context = memory_service.get_relevant_context(test_query, k=2)
    print("\nRetrieved Context:")
    print(context)
    
    print("\nMemoryService tests completed successfully.")
