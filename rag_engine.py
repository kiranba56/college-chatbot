import json
import os
import re
import math
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from config import Config
from database import db

logger = logging.getLogger(__name__)

class RAGEngine:
    """
    Retrieval-Augmented Generation (RAG) engine for College Information.
    Combines:
    - Semantic Embeddings (Gemini text-embedding-004 / Local Cosine Similarity)
    - Vector Database Retrieval (Supabase pgvector / Local vector store)
    - LLM Answer Generation (Gemini 2.5/1.5 Flash API)
    """

    def __init__(self, data_path: str = None):
        self.data_path = data_path or os.path.join(os.path.dirname(__file__), "data", "college_knowledge.json")
        self.documents: List[Dict[str, Any]] = []
        self.local_vocab: Dict[str, int] = {}
        self.doc_vectors: List[np.ndarray] = []
        self.gemini_client = None
        self._init_ai_client()
        self.load_documents()

    def _init_ai_client(self):
        """Initialize Google GenAI client if API key is present."""
        if Config.GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
                logger.info("Google GenAI client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize google.genai: {e}. Trying google.generativeai...")
                try:
                    import google.generativeai as legacy_genai
                    legacy_genai.configure(api_key=Config.GEMINI_API_KEY)
                    self.gemini_client = "legacy"
                    logger.info("Legacy google.generativeai configured.")
                except Exception as e2:
                    logger.error(f"Failed to configure Gemini API: {e2}")

    def load_documents(self):
        """Load knowledge base documents and initialize local vectors."""
        # Initialize SQLite database with seed data if needed
        db.init_db(self.data_path)
        docs = db.get_all_documents()
        
        if docs:
            self.documents = docs
            logger.info(f"Loaded {len(self.documents)} college knowledge entries from Flask SQLite database.")
        elif os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
                logger.info(f"Loaded {len(self.documents)} college knowledge entries from JSON.")
            except Exception as e:
                logger.error(f"Error loading knowledge documents: {e}")
        
        self._build_local_vectors()

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer for semantic TF-IDF local fallback."""
        text = text.lower()
        tokens = re.findall(r'\b[a-z0-9_-]{2,}\b', text)
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'in', 'of', 'for', 'to',
            'with', 'about', 'by', 'as', 'into', 'like', 'through', 'after', 'over', 'between',
            'out', 'against', 'during', 'without', 'before', 'under', 'around', 'among', 'what',
            'where', 'when', 'how', 'who', 'does', 'can', 'are', 'i', 'my', 'please', 'tell', 'me'
        }
        return [t for t in tokens if t not in stop_words]

    def _build_local_vectors(self):
        """Build TF-IDF based vector representations for high-speed local vector search."""
        vocab = {}
        doc_token_lists = []

        for doc in self.documents:
            full_text = f"{doc.get('title', '')} {doc.get('category', '')} {doc.get('content', '')} {' '.join(doc.get('keywords', []))}"
            tokens = self._tokenize(full_text)
            doc_token_lists.append(tokens)
            for t in tokens:
                vocab[t] = vocab.get(t, 0) + 1

        # Keep vocabulary
        self.local_vocab = {term: idx for idx, (term, count) in enumerate(vocab.items())}
        num_docs = len(self.documents)
        vocab_size = len(self.local_vocab)

        if vocab_size == 0 or num_docs == 0:
            return

        # Compute IDF
        idf = np.zeros(vocab_size)
        for tokens in doc_token_lists:
            unique_tokens = set(tokens)
            for t in unique_tokens:
                if t in self.local_vocab:
                    idf[self.local_vocab[t]] += 1
        self.idf = np.log((num_docs + 1) / (idf + 1)) + 1.0

        # Compute TF-IDF vectors for all documents
        self.doc_vectors = []
        for tokens in doc_token_lists:
            vec = np.zeros(vocab_size)
            for t in tokens:
                if t in self.local_vocab:
                    vec[self.local_vocab[t]] += 1
            # Normalize
            vec = vec * self.idf
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            self.doc_vectors.append(vec)

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generates embedding using Gemini API if key exists.
        Returns a list of floats (768 dimensions).
        """
        if not Config.GEMINI_API_KEY:
            return None

        try:
            if self.gemini_client and self.gemini_client != "legacy":
                response = self.gemini_client.models.embed_content(
                    model=Config.GEMINI_EMBEDDING_MODEL,
                    contents=text
                )
                if hasattr(response, 'embedding') and hasattr(response.embedding, 'values'):
                    return list(response.embedding.values)
                elif hasattr(response, 'embeddings') and len(response.embeddings) > 0:
                    return list(response.embeddings[0].values)
            elif self.gemini_client == "legacy":
                import google.generativeai as legacy_genai
                result = legacy_genai.embed_content(
                    model=Config.GEMINI_EMBEDDING_MODEL,
                    content=text,
                    task_type="retrieval_query"
                )
                return result.get('embedding', [])
        except Exception as e:
            logger.warning(f"Error calling Gemini Embedding API: {e}")
        return None

    def retrieve(self, query: str, category: Optional[str] = None, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Retrieves top relevant college documents natively in Flask.
        Performs high-speed semantic vector search (cosine similarity + TF-IDF) with keyword boosting.
        """
        category_clean = (category.lower().strip() if category and category.lower() != "all" else None)
        return self._local_vector_search(query, category_clean, top_k)

    def _local_vector_search(self, query: str, category: Optional[str], top_k: int = 4) -> List[Dict[str, Any]]:
        """Compute cosine similarity against local document vectors."""
        if not self.local_vocab or len(self.doc_vectors) == 0:
            return self.documents[:top_k]

        query_tokens = self._tokenize(query)
        q_vec = np.zeros(len(self.local_vocab))
        for t in query_tokens:
            if t in self.local_vocab:
                q_vec[self.local_vocab[t]] += 1

        q_vec = q_vec * self.idf
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        scored_docs = []
        query_words = set(query.lower().split())

        for idx, doc in enumerate(self.documents):
            # Category filter
            if category and doc.get("category", "").lower() != category:
                continue

            # Cosine similarity
            cos_sim = float(np.dot(q_vec, self.doc_vectors[idx])) if q_norm > 0 else 0.0

            # Boost if keywords match query
            kw_boost = 0.0
            doc_keywords = [k.lower() for k in doc.get("keywords", [])]
            for kw in doc_keywords:
                if any(w in kw for w in query_words):
                    kw_boost += 0.15

            # Boost if title matches
            title_lower = doc.get("title", "").lower()
            if any(w in title_lower for w in query_words if len(w) > 3):
                kw_boost += 0.20

            final_score = min(cos_sim + kw_boost, 1.0)

            scored_docs.append({
                "id": doc.get("id"),
                "category": doc.get("category"),
                "title": doc.get("title"),
                "content": doc.get("content"),
                "similarity": round(final_score, 3)
            })

        # Sort by similarity descending
        scored_docs.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_docs[:top_k]

    def generate_answer(self, query: str, retrieved_docs: List[Dict[str, Any]], history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        RAG Generation step:
        Uses LLM (Gemini) with retrieved verified context to answer student queries accurately.
        """
        # Build context block
        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            context_parts.append(
                f"[Source {i} | Category: {doc.get('category', '').upper()} | Title: {doc.get('title', '')}]\n{doc.get('content', '')}"
            )
        context_str = "\n\n".join(context_parts) if context_parts else "No specific documents found."

        # If Gemini API is available, generate via LLM
        if Config.GEMINI_API_KEY:
            try:
                llm_response = self._call_gemini_llm(query, context_str, history)
                if llm_response:
                    return {
                        "reply": llm_response,
                        "sources": retrieved_docs,
                        "model": Config.GEMINI_LLM_MODEL,
                        "used_rag": True
                    }
            except Exception as e:
                logger.error(f"Error calling Gemini LLM: {e}")

        # Fallback generator: Synthesizes rich, structured response from retrieved context
        fallback_reply = self._synthesize_fallback_answer(query, retrieved_docs)
        return {
            "reply": fallback_reply,
            "sources": retrieved_docs,
            "model": "Campus RAG Engine (Verified Knowledge Base)",
            "used_rag": True
        }

    def _call_gemini_llm(self, query: str, context: str, history: List[Dict[str, str]] = None) -> Optional[str]:
        """Constructs prompt and calls Gemini model."""
        system_instruction = f"""You are 'CampusAI', the official AI student advisor and campus assistant for {Config.COLLEGE_NAME}.
Your primary goal is to help students, parents, faculty, and visitors find accurate, clear, and instant answers regarding:
- College timings, operating hours & bus schedules
- Academic departments, courses, curriculum & electives
- Faculty directory, cabin locations, and consultation hours
- Fee structures, payment deadlines, portal steps & installment plans
- Examinations, mid-term & end-term schedules, 75% attendance rule, CGPA grading & backlogs
- Campus placements, average/highest CTC packages, eligibility, and internships
- Institutional & government scholarships, eligibility & application steps
- Classrooms, block navigation (Newton Block, Turing Block, etc.), Wi-Fi & campus facilities
- Student clubs, technical fests (Aura, InnovateX, Hackathons) & extracurriculars.

RULES:
1. Ground your answers firmly on the provided COLLEGE KNOWLEDGE CONTEXT below.
2. If the context contains the answer, be comprehensive, warm, encouraging, and clear.
3. Format your response cleanly using Markdown:
   - Use bold text for key deadlines, office cabins, phone extensions, room numbers, and timings.
   - Use bullet points or numbered lists where steps or options are explained.
   - Use markdown tables if comparing multiple options or fee slabs.
4. If the exact answer is not in the context, politely state what you know and guide the student to the relevant department (e.g. Student Section Counter 3, Dean Academics, or HOD Cabin).
5. Always maintain a professional, helpful, collegiate tone.
6. Answer ONLY the specific question asked. Do NOT append unsolicited 'Related Information' or General Gate Operating Hours unless the user explicitly asks for them.

COLLEGE KNOWLEDGE CONTEXT:
{context}
"""

        user_prompt = f"Student Question: {query}\n\nPlease provide a clear, helpful, and structured answer based on the college records above."

        try:
            if self.gemini_client and self.gemini_client != "legacy":
                response = self.gemini_client.models.generate_content(
                    model=Config.GEMINI_LLM_MODEL,
                    contents=user_prompt,
                    config={
                        "system_instruction": system_instruction,
                        "temperature": 0.3,
                        "max_output_tokens": 1000
                    }
                )
                if response and hasattr(response, 'text'):
                    return response.text
            elif self.gemini_client == "legacy":
                import google.generativeai as legacy_genai
                model = legacy_genai.GenerativeModel(
                    model_name=Config.GEMINI_LLM_MODEL,
                    system_instruction=system_instruction
                )
                chat = model.start_chat()
                resp = chat.send_message(user_prompt)
                return resp.text
        except Exception as e:
            logger.error(f"Gemini LLM generation failed: {e}")
        return None

    def _synthesize_fallback_answer(self, query: str, retrieved_docs: List[Dict[str, Any]]) -> str:
        """
        Creates a high-quality, formatted answer directly from retrieved knowledge chunks
        when an external LLM API key is not configured or offline.
        """
        if not retrieved_docs or retrieved_docs[0].get("similarity", 0) < 0.15:
            return (
                f"### Information Notice\n\n"
                f"I couldn't find an exact match for **\"{query}\"** in our official campus knowledge records.\n\n"
                f"**Here are recommended places to check:**\n"
                f"- **Administrative Office / Student Section:** Ground Floor, Admin Block (Counter 3 & 4)\n"
                f"- **Academic Queries:** Dean of Academics Cabin AB-104 (Mon-Fri: 11:00 AM - 12:30 PM)\n"
                f"- **ERP Portal:** [https://erp.college.edu](https://erp.college.edu)\n"
                f"- **Helpline Email:** `support@college.edu`\n\n"
                f"*Tip: You can select one of the category chips above (Timings, Fees, Exams, Placements, Faculty) to browse specific campus details!*"
            )

        top_doc = retrieved_docs[0]
        content = top_doc.get("content", "")
        title = top_doc.get("title", "")
        category = top_doc.get("category", "General").title()

        response_md = f"### 📌 {title}\n*Category: {category}*\n\n"
        response_md += f"{content}"

        return response_md

    def generate_suggested_questions(self, query: str, category: Optional[str] = None) -> List[str]:
        """Provides smart suggested follow-up questions."""
        q_lower = query.lower()
        if "fee" in q_lower or "pay" in q_lower or category == "fees":
            return [
                "What is the fee payment deadline and late fine policy?",
                "Are there any merit-based scholarships or fee waivers?",
                "What are the hostel and mess charges?"
            ]
        elif "time" in q_lower or "hour" in q_lower or "schedule" in q_lower or category == "timings":
            return [
                "What are the Central Library timings on weekends?",
                "When do the college buses depart in the evening?",
                "What are the Administrative Office counter timings?"
            ]
        elif "exam" in q_lower or "result" in q_lower or "grade" in q_lower or category == "examinations":
            return [
                "What is the minimum attendance required for exam eligibility?",
                "How do I apply for paper re-evaluation and verification?",
                "What is the internal vs end-semester mark distribution?"
            ]
        elif "place" in q_lower or "salary" in q_lower or "package" in q_lower or category == "placements":
            return [
                "What are the eligibility criteria for campus placement drives?",
                "What was the highest and average CTC package this year?",
                "How can I get an NOC for an off-campus 8th-semester internship?"
            ]
        elif "facult" in q_lower or "prof" in q_lower or "hod" in q_lower or category == "faculty":
            return [
                "Who is the HOD of Computer Science and what are his consultation hours?",
                "Where is the ECE Department located?",
                "How can I contact the Dean of Academics?"
            ]
        elif "room" in q_lower or "class" in q_lower or "block" in q_lower or category == "facilities":
            return [
                "Where is Alan Turing Block and what labs are on the 3rd floor?",
                "How do I connect to CampusNet Wi-Fi?",
                "Is the campus health centre and doctor available 24/7?"
            ]
        else:
            return [
                "What are the general college and gate timings?",
                "How do I apply for national and state scholarships?",
                "What annual fests and hackathons are hosted on campus?"
            ]

    def reindex_documents(self) -> Dict[str, Any]:
        """Reloads all documents from SQLite / JSON and rebuilds vector representations in Flask."""
        self.load_documents()
        return {
            "success": True,
            "message": f"Successfully re-indexed {len(self.documents)} documents in Flask vector database.",
            "synced_count": len(self.documents),
            "total_documents": len(self.documents)
        }

    def sync_to_supabase(self) -> Dict[str, Any]:
        """Backwards compatibility alias for re-indexing in Flask."""
        return self.reindex_documents()

# Global singleton RAG instance
rag_engine = RAGEngine()
