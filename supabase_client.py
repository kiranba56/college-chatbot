import logging
from config import Config

logger = logging.getLogger(__name__)

class SupabaseManager:
    """Manages connections and operations with Supabase pgvector database."""
    
    def __init__(self):
        self.client = None
        self.url = Config.SUPABASE_URL
        self.key = Config.SUPABASE_KEY
        self._initialize_client()

    def _initialize_client(self):
        if not self.url or not self.key:
            logger.info("Supabase URL or Key not set. Running in local vector mode.")
            return

        try:
            from supabase import create_client, Client
            self.client: Client = create_client(self.url, self.key)
            logger.info("Successfully connected to Supabase client!")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            self.client = None

    def is_connected(self) -> bool:
        return self.client is not None

    def match_documents(self, query_embedding: list, match_threshold: float = 0.20, match_count: int = 4, category: str = None):
        """Call the match_documents stored procedure in PostgreSQL via Supabase RPC."""
        if not self.is_connected():
            return None

        try:
            params = {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count,
                "filter_category": category if category and category != "all" else None
            }
            response = self.client.rpc("match_documents", params).execute()
            if hasattr(response, 'data') and response.data:
                return response.data
            return []
        except Exception as e:
            logger.error(f"Supabase match_documents RPC error: {e}")
            return None

    def upsert_document(self, doc_id: str, category: str, title: str, content: str, keywords: list = None, embedding: list = None):
        """Insert or update a document with its vector embedding in Supabase."""
        if not self.is_connected():
            return False

        try:
            payload = {
                "id": doc_id,
                "category": category,
                "title": title,
                "content": content,
                "keywords": keywords or [],
            }
            if embedding:
                payload["embedding"] = embedding

            response = self.client.table("college_documents").upsert(payload).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Supabase upsert_document error: {e}")
            return False

    def log_chat(self, user_query: str, bot_response: str, category: str = None, sources: list = None, session_id: str = None):
        """Log chat interactions to Supabase for analysis and feedback tracking."""
        if not self.is_connected():
            return None

        try:
            payload = {
                "session_id": session_id or "default-session",
                "user_query": user_query,
                "bot_response": bot_response,
                "category": category,
                "sources": sources or [],
                "feedback": 0
            }
            response = self.client.table("chat_logs").insert(payload).execute()
            if response.data and len(response.data) > 0:
                return response.data[0].get("id")
        except Exception as e:
            logger.error(f"Error logging chat to Supabase: {e}")
        return None

    def update_feedback(self, log_id: int, feedback: int):
        """Record user feedback (1 for positive, -1 for negative)."""
        if not self.is_connected() or not log_id:
            return False

        try:
            self.client.table("chat_logs").update({"feedback": feedback}).eq("id", log_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating feedback in Supabase: {e}")
            return False

# Global instance
supabase_mgr = SupabaseManager()
