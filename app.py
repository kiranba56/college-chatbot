import os
import sys
import json
import logging

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from config import Config
from rag_engine import rag_engine
from database import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Initialize Flask native SQLite database
db.init_db(rag_engine.data_path)

# Categories configuration with icons and descriptions
CATEGORIES = [
    {
        "id": "all",
        "name": "All Topics",
        "icon": "fas fa-sparkles",
        "badge": "All",
        "sample": "How does the academic year work here?"
    },
    {
        "id": "timings",
        "name": "Timings & Hours",
        "icon": "fas fa-clock",
        "badge": "Timings",
        "sample": "What are the Central Library timings on weekends?"
    },
    {
        "id": "departments",
        "name": "Departments",
        "icon": "fas fa-building-columns",
        "badge": "Depts",
        "sample": "Where is the Computer Science Department located?"
    },
    {
        "id": "faculty",
        "name": "Faculty Directory",
        "icon": "fas fa-chalkboard-user",
        "badge": "Faculty",
        "sample": "Who is the HOD of CSE and when are his office hours?"
    },
    {
        "id": "courses",
        "name": "Courses & Credits",
        "icon": "fas fa-book-bookmark",
        "badge": "Courses",
        "sample": "What are the credit requirements for B.Tech degree?"
    },
    {
        "id": "fees",
        "name": "Fees & Payments",
        "icon": "fas fa-receipt",
        "badge": "Fees",
        "sample": "What is the tuition fee and installment deadline?"
    },
    {
        "id": "examinations",
        "name": "Exams & Results",
        "icon": "fas fa-graduation-cap",
        "badge": "Exams",
        "sample": "What is the 75% attendance rule for semester exams?"
    },
    {
        "id": "placements",
        "name": "Placements & Internships",
        "icon": "fas fa-briefcase",
        "badge": "Careers",
        "sample": "What was the highest package and top recruiting companies?"
    },
    {
        "id": "scholarships",
        "name": "Scholarships & Aid",
        "icon": "fas fa-award",
        "badge": "Aid",
        "sample": "How can I apply for institutional merit scholarships?"
    },
    {
        "id": "facilities",
        "name": "Campus & Classrooms",
        "icon": "fas fa-map-location-dot",
        "badge": "Campus",
        "sample": "How do I find room TB-301 in Turing Block and connect to Wi-Fi?"
    },
    {
        "id": "events",
        "name": "Events & Clubs",
        "icon": "fas fa-calendar-star",
        "badge": "Events",
        "sample": "When is the annual cultural fest Aura and how do I join clubs?"
    }
]

@app.route('/')
def home():
    """Render the single-page College Chatbot application."""
    return render_template(
        'index.html',
        college_name=Config.COLLEGE_NAME,
        college_short_name=Config.COLLEGE_SHORT_NAME,
        categories=CATEGORIES
    )

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main conversational RAG endpoint for student queries."""
    try:
        data = request.get_json(force=True)
        query = data.get('message', '').strip()
        category = data.get('category', 'all')
        session_id = data.get('session_id', 'session_guest')
        history = data.get('history', [])

        if not query:
            return jsonify({"error": "Query message cannot be empty"}), 400

        # Step 1: Vector Retrieval (Supabase pgvector / Local vector store)
        retrieved_docs = rag_engine.retrieve(query=query, category=category, top_k=Config.TOP_K_RESULTS)

        # Step 2: Generation via LLM + retrieved knowledge
        generation_result = rag_engine.generate_answer(query=query, retrieved_docs=retrieved_docs, history=history)

        reply = generation_result.get("reply", "")
        sources = generation_result.get("sources", [])
        model = generation_result.get("model", "CampusAI")

        # Step 3: Dynamic suggested follow-ups
        suggested_questions = rag_engine.generate_suggested_questions(query=query, category=category)

        # Step 4: Log chat interaction to Flask native database
        log_id = db.log_chat(
            user_query=query,
            bot_response=reply,
            category=category,
            sources=sources,
            session_id=session_id
        )

        return jsonify({
            "success": True,
            "reply": reply,
            "sources": sources,
            "suggested_questions": suggested_questions,
            "model": model,
            "log_id": log_id,
            "category": category
        })

    except Exception as e:
        logger.error(f"Error in /api/chat: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An internal server error occurred while processing your query.",
            "details": str(e)
        }), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Return available campus categories and quick prompts."""
    return jsonify({
        "success": True,
        "categories": CATEGORIES
    })

@app.route('/api/knowledge', methods=['GET'])
def get_knowledge():
    """Browse or search knowledge base records for the directory explorer."""
    category = request.args.get('category', 'all').lower().strip()
    search = request.args.get('search', '').lower().strip()

    docs = db.get_all_documents(category=category, search=search)
    return jsonify({
        "success": True,
        "count": len(docs),
        "documents": docs
    })

@app.route('/api/knowledge', methods=['POST'])
def add_knowledge():
    """Add a new campus notice, policy, or information record."""
    try:
        data = request.get_json(force=True)
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        category = data.get('category', 'general').strip().lower()
        keywords = data.get('keywords', [])

        if not title or not content:
            return jsonify({"error": "Title and content are required"}), 400

        doc_id = f"custom-{len(rag_engine.documents) + 1:03d}"
        new_doc = {
            "id": doc_id,
            "category": category,
            "title": title,
            "content": content,
            "keywords": keywords if isinstance(keywords, list) else [k.strip() for k in keywords.split(',') if k.strip()]
        }

        # Persist to Flask SQLite database
        db.upsert_document(
            doc_id=doc_id,
            category=category,
            title=title,
            content=content,
            keywords=new_doc["keywords"]
        )

        # Append to documents list
        rag_engine.documents.append(new_doc)
        
        # Save back to JSON file
        try:
            with open(rag_engine.data_path, 'w', encoding='utf-8') as f:
                json.dump(rag_engine.documents, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist to file: {e}")

        # Rebuild local vector store
        rag_engine._build_local_vectors()

        return jsonify({
            "success": True,
            "message": "Notice added successfully to campus knowledge base!",
            "document": new_doc
        })

    except Exception as e:
        logger.error(f"Error adding knowledge: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit positive/negative student rating for RAG response tuning."""
    try:
        data = request.get_json(force=True)
        log_id = data.get('log_id')
        feedback = data.get('feedback', 0) # 1 or -1

        if log_id:
            db.update_feedback(int(log_id), feedback)

        return jsonify({
            "success": True,
            "message": "Feedback recorded. Thank you for helping improve CampusAI!"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Return backend, Flask SQLite database, and AI model health diagnostics."""
    stats = db.get_stats()
    return jsonify({
        "status": "online",
        "college_name": Config.COLLEGE_NAME,
        "backend_framework": "Flask 3.x (Python)",
        "database": "Flask Native SQLite (Local & Persistent)",
        "database_connected": True,
        "gemini_api_configured": bool(Config.GEMINI_API_KEY),
        "total_documents_indexed": len(rag_engine.documents),
        "llm_model": Config.GEMINI_LLM_MODEL,
        "embedding_model": Config.GEMINI_EMBEDDING_MODEL,
        "stats": stats
    })

@app.route('/api/sync-supabase', methods=['POST'])
@app.route('/api/reindex', methods=['POST'])
def sync_database():
    """Re-index all documents in Flask native database and vector engine."""
    result = rag_engine.reindex_documents()
    return jsonify(result)

if __name__ == '__main__':
    print(f"==================================================")
    print(f"🎓 Starting {Config.COLLEGE_NAME} Chatbot")
    print(f"🚀 Running on http://127.0.0.1:{Config.PORT}")
    print(f"📡 Backend: 100% Flask Native (SQLite + Local Vector RAG)")
    print(f"🧠 AI Provider: {'Gemini API Configured' if Config.GEMINI_API_KEY else 'Smart Verified RAG Fallback'}")
    print(f"==================================================")
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
