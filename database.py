"""
Flask Native SQLite Database Manager for College Chatbot.
Provides local persistent storage for knowledge documents, chat history, and feedback.
Zero external cloud or Supabase dependencies.
"""
import sqlite3
import json
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = os.path.join(os.path.dirname(__file__), "data")
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, "college_chatbot.db")
        else:
            self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self, seed_json_path: Optional[str] = None):
        """Initialize SQLite tables for documents, chat logs, and feedback."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Documents Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS college_documents (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Chat Logs & Feedback Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_query TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    category TEXT,
                    sources TEXT DEFAULT '[]',
                    feedback INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

        # Seed from JSON if documents table is empty
        if seed_json_path and os.path.exists(seed_json_path):
            self._seed_from_json_if_empty(seed_json_path)

    def _seed_from_json_if_empty(self, json_path: str):
        """Seed the SQLite database from college_knowledge.json if documents table is empty."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM college_documents")
            count = cursor.fetchone()[0]
            if count == 0:
                logger.info(f"Seeding Flask SQLite database from {json_path}...")
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        docs = json.load(f)
                    for doc in docs:
                        cursor.execute("""
                            INSERT OR REPLACE INTO college_documents (id, category, title, content, keywords)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            doc.get('id', ''),
                            doc.get('category', 'general'),
                            doc.get('title', ''),
                            doc.get('content', ''),
                            json.dumps(doc.get('keywords', []))
                        ))
                    conn.commit()
                    logger.info(f"Seeded {len(docs)} documents into Flask SQLite database.")
                except Exception as e:
                    logger.error(f"Error seeding database from JSON: {e}")

    def get_all_documents(self, category: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve documents with optional category or keyword filter."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, category, title, content, keywords FROM college_documents WHERE 1=1"
            params = []

            if category and category.lower() != 'all':
                query += " AND LOWER(category) = LOWER(?)"
                params.append(category.strip())

            if search:
                query += " AND (LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(keywords) LIKE ?)"
                search_param = f"%{search.lower()}%"
                params.extend([search_param, search_param, search_param])

            query += " ORDER BY category ASC, title ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            results = []
            for r in rows:
                try:
                    kw = json.loads(r['keywords'])
                except Exception:
                    kw = [k.strip() for k in (r['keywords'] or '').split(',') if k.strip()]
                results.append({
                    "id": r['id'],
                    "category": r['category'],
                    "title": r['title'],
                    "content": r['content'],
                    "keywords": kw
                })
            return results

    def upsert_document(self, doc_id: str, category: str, title: str, content: str, keywords: List[str]) -> bool:
        """Insert or update a document in the Flask database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO college_documents (id, category, title, content, keywords)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    doc_id,
                    category,
                    title,
                    content,
                    json.dumps(keywords if isinstance(keywords, list) else [keywords])
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error upserting document {doc_id}: {e}")
            return False

    def log_chat(self, user_query: str, bot_response: str, category: Optional[str] = None, sources: Optional[List[Any]] = None, session_id: Optional[str] = None) -> Optional[int]:
        """Save student chat interaction to Flask SQLite database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chat_logs (session_id, user_query, bot_response, category, sources, feedback)
                    VALUES (?, ?, ?, ?, ?, 0)
                """, (
                    session_id or "session_default",
                    user_query,
                    bot_response,
                    category or "all",
                    json.dumps(sources or [])
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error logging chat in Flask SQLite: {e}")
            return None

    def update_feedback(self, log_id: int, feedback: int) -> bool:
        """Record user feedback (1 for positive, -1 for negative)."""
        if not log_id:
            return False
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE chat_logs SET feedback = ? WHERE id = ?", (feedback, log_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating feedback for log {log_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get summary metrics for diagnostics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM college_documents")
            doc_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM chat_logs")
            log_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE feedback = 1")
            positive_feedback = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE feedback = -1")
            negative_feedback = cursor.fetchone()[0]

            return {
                "total_documents": doc_count,
                "total_chats": log_count,
                "positive_feedback": positive_feedback,
                "negative_feedback": negative_feedback,
                "database_engine": "Flask SQLite (Local & Persistent)"
            }

# Global singleton database instance
db = DatabaseManager()
