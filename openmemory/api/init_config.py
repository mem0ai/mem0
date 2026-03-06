"""Seed the OpenMemory SQLite DB with Ollama+FAISS config on first boot."""
import json
import os
import sys
import uuid
import datetime

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.database import Base, SessionLocal, engine
from app.models import Config as ConfigModel

OLLAMA_CONFIG = {
    "openmemory": {
        "custom_instructions": None
    },
    "mem0": {
        "llm": {
            "provider": "ollama",
            "config": {
                "model": "llama3.2:3b",
                "ollama_base_url": "http://localhost:11434",
                "temperature": 0.1,
                "max_tokens": 2000
            }
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text:latest",
                "ollama_base_url": "http://localhost:11434"
            }
        },
        "vector_store": {
            "provider": "faiss",
            "config": {
                "collection_name": "openmemory",
                "path": "/Users/mirror-admin/.mirrordna/openmemory/faiss",
                "embedding_model_dims": 768,
                "distance_strategy": "cosine"
            }
        }
    }
}

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
        if existing:
            existing.value = OLLAMA_CONFIG
            existing.updated_at = datetime.datetime.utcnow()
            print("Updated existing config → Ollama+FAISS")
        else:
            cfg = ConfigModel(
                id=uuid.uuid4(),
                key="main",
                value=OLLAMA_CONFIG,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow(),
            )
            db.add(cfg)
            print("Inserted new config → Ollama+FAISS")
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
    print("Done.")
