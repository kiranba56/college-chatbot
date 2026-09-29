import os
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

class Config:
    COLLEGE_NAME = os.getenv("COLLEGE_NAME", "National Institute of Science & Technology (NIST)")
    COLLEGE_SHORT_NAME = os.getenv("COLLEGE_SHORT_NAME", "NIST Campus AI")
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

    # AI Configuration (Gemini API / OpenAI API)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    
    # Models
    GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004")
    GEMINI_LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-1.5-flash")
    
    # Vector Search Parameters
    TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", 4))
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.20))
