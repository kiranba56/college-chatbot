# 🎓 College AI Chatbot (RAG + Supabase + LLM)

An enterprise-grade, intelligent digital campus assistant designed to solve information fragmentation across universities. Students, parents, faculty, and prospective students can ask questions in natural language and receive immediate, verified answers regarding **timings, departments, faculty directory, courses, fees, exams, placements, scholarships, classrooms, and facilities**.

---

## 🌟 Tech Stack & Architecture

- **Frontend**: Semantic HTML5, Glassmorphic Vanilla CSS (modern dark/light design system), Responsive JavaScript (Voice-to-Text via Web Speech API, Text-to-Speech audio reading, Markdown rendering with tables, dynamic follow-up chips).
- **Backend**: Python 3.13, Flask 3.1, Flask-CORS.
- **Database**: **Supabase** (PostgreSQL with `pgvector` extension for semantic vector similarity search) + Chat logging & feedback capture.
- **AI & RAG Pipeline**:
  - **Embeddings**: Google Gemini `text-embedding-004` (768 dimensions) + local cosine similarity vector fallback.
  - **Vector Retrieval**: Supabase PostgreSQL RPC `match_documents` (HNSW cosine similarity index) + keyword boost.
  - **LLM Generation**: Google Gemini 1.5/2.5 Flash API with custom collegiate system instructions and grounding.

---

## 📁 Project Structure

```
College Chatbot/
├── app.py                     # Flask web server & REST endpoints
├── config.py                  # Environment & model settings loader
├── rag_engine.py              # RAG pipeline, embedding vectorization & retrieval
├── supabase_client.py         # Supabase connection & RPC query manager
├── supabase_schema.sql        # Ready-to-run PostgreSQL schema for Supabase
├── run.py                     # Quick launcher script
├── requirements.txt           # Python dependencies
├── .env                       # Active configuration file
├── .env.example               # Example template for credentials
├── data/
│   └── college_knowledge.json # Comprehensive 10-domain campus knowledge base
├── static/
│   ├── css/
│   │   └── style.css          # Glassmorphic CSS design system (Dark & Light)
│   └── js/
│       └── app.js             # Client interactivity, Speech API, RAG streaming UI
└── templates/
    └── index.html             # Responsive single-page web app
```

---

## 🚀 Quick Start Guide

### 1. Run the Chatbot
Open your terminal in the `College Chatbot` directory and execute:
```bash
python run.py
```
Then visit **`http://127.0.0.1:5000`** in your browser!

> 💡 **Zero-Config Ready**: The application includes a high-performance local vector similarity engine, so it works **instantly** out of the box with all campus topics even before you connect external cloud API keys!

---

## ⚡ Connecting Supabase (Vector Database)

1. Sign in to your [Supabase Dashboard](https://supabase.com) and create a project (free tier).
2. Go to **SQL Editor** in your Supabase dashboard.
3. Open `supabase_schema.sql` from this project, copy its contents, paste them into the Supabase SQL editor, and click **Run**.
   - This enables the `vector` extension.
   - Creates the `college_documents` table with vector embeddings.
   - Creates the `match_documents` cosine similarity search function.
   - Creates the `chat_logs` table.
4. Go to **Project Settings -> API** in Supabase:
   - Copy **Project URL**
   - Copy **Project API Key** (`anon` or `service_role`)
5. Open `.env` in the `College Chatbot` folder and fill in:
   ```env
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your-supabase-anon-or-service-key
   ```
6. Open the chatbot UI, click **System Info** in the top navigation, and click **Sync All Documents to Supabase**!

---

## 🧠 Connecting Gemini AI (LLM & Embeddings)

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Open `.env` and paste:
   ```env
   GEMINI_API_KEY=AIzaSy...your-gemini-key
   ```
3. Restart the server. The chatbot will now use Gemini 1.5/2.5 Flash for natural responses grounded on your campus knowledge base!

---

## 🎓 Verified Campus Knowledge Domains Covered

1. **College Timings & Gate Rules**: General hours, weekend schedules, entry gate closing times, evening bus departure shifts.
2. **Central Library**: Working hours (8:00 AM - 9:00 PM), exam night reading hall extensions, book borrowing limits, IEEE digital library access.
3. **Academic Departments**: CSE, ECE, Mechanical, Civil, AI & Data Science, Management (MBA).
4. **Faculty Directory**: HOD profiles, cabin numbers (e.g. TB-301), consultation hours, and emails.
5. **Courses & Credits**: B.Tech degree branches, Choice Based Credit System (160 credits), minor degree tracks.
6. **Fees & Payments**: Tuition breakdown, hostel & mess charges, ERP payment portal guidelines, bank NEFT details, late fine policy.
7. **Examinations & Hall Tickets**: Internal 1 & 2 schedules, 75% attendance rule, CGPA grading scale, re-evaluation and backlog exams.
8. **Placements & Internships**: Highest package (44.5 LPA), average package (7.8 LPA), top recruiters (Microsoft, Amazon, Cisco, TCS), eligibility criteria, 8th-sem internship NOC.
9. **Scholarships & Financial Aid**: Chairman's 100% merit scholarship, branch topper awards, NSP/State Post-Matric schemes, documents required.
10. **Campus Facilities & Classrooms**: Room locator (Newton Block NB-101 to NB-320, Turing Block TB-101 to TB-420), CampusNet Wi-Fi login, health clinic & 24/7 ambulance.

---

## 🔌 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/chat` | Main RAG query endpoint (`{ message, category, session_id }`) |
| `GET` | `/api/categories` | Returns category definitions, icons, and sample queries |
| `GET` | `/api/knowledge` | Knowledge directory explorer with search and category filters |
| `POST` | `/api/knowledge` | Publish and index a new campus notice/policy |
| `POST` | `/api/feedback` | Record student thumbs up/down rating for RAG tuning |
| `GET` | `/api/status` | Diagnostic health check (Supabase, Gemini, document count) |
| `POST` | `/api/sync-supabase`| Upserts all knowledge items with vector embeddings to Supabase |
