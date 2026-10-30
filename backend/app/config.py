import os

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "100"))
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dims; must match schema.sql
TOP_K = 5
CANDIDATES = 20  # per retriever, before fusion
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
