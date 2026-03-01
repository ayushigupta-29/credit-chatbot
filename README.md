# Credit Chatbot

An AI-powered chatbot that answers user queries related to credit education — scores, loans, credit cards, and credit reports. Built for the Indian financial context.

Answers are grounded in a curated knowledge base using RAG (Retrieval Augmented Generation), so responses are accurate and source-attributed — not hallucinated.

![Python](https://img.shields.io/badge/Python-3.13-blue) ![Mistral](https://img.shields.io/badge/LLM-Mistral%207B-orange) ![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)

---

## What it does
- Answers credit education questions in plain English
- Retrieves relevant context from a curated knowledge base before answering
- Shows source documents used for each answer (fully transparent)
- Maintains conversation history for natural follow-up questions
- Phone login + consent-gated personalised answers from user's actual bureau data
- Runs entirely locally — no API costs, no data leaving your machine

## How it works (RAG Architecture)
```
User Question
     ↓
[Embedding model converts question to vector]
     ↓
[ChromaDB finds most semantically similar chunks from knowledge base]
     ↓
[Optional: user's personal bureau profile injected if logged in + consented]
     ↓
[Mistral 7B / LLaMA 3.2 receives: system prompt + context + question]
     ↓
Answer (streamed live) + Sources shown
```

## Knowledge Base
The chatbot answers from curated documents covering:
- Credit score fundamentals (CIBIL, Experian, CRIF, Equifax)
- How to improve your credit score
- Credit cards and utilisation
- Loans, EMIs, interest rates, and key terms
- Credit reports and how to dispute errors
- Frequently asked questions
- Score driver reference — all tracked factors with polarity (generated from `score_drivers.db`)
- Bureau parameters and scoring methodology *(encrypted)*
- Score movement patterns from real scrub data *(encrypted)*

## Tech Stack
| Layer | Tool |
|---|---|
| LLM | Mistral 7B / LLaMA 3.2 3B via Ollama (runs locally) |
| Embeddings | sentence-transformers / all-MiniLM-L6-v2 |
| Vector DB | ChromaDB (local) |
| Orchestration | LangChain |
| UI | Streamlit |
| Customer data DB | SQLite (in-memory at runtime, never written to disk in plaintext) |
| Encryption | Fernet (AES-128) for sensitive KB docs and customer bureau DB |

## Project Structure
```
credit-chatbot/
├── knowledge_base/
│   ├── 01_credit_score_fundamentals.md
│   ├── 02_improving_credit_score.md
│   ├── 03_credit_cards.md
│   ├── 04_loans_and_credit.md
│   ├── 05_credit_reports.md
│   ├── 06_faqs.md
│   ├── 07_score_patterns.md.enc          # encrypted — requires .env key
│   ├── 08_bureau_parameters.md.enc       # encrypted — requires .env key
│   ├── 09_score_driver_reference.md      # generated — run generate_kb_drivers.py
│   └── data_dictionary/
│       └── experian_scrub_dictionary_jan2026.pdf.enc
├── data/
│   ├── score_drivers.db                  # plain reference DB — no PII, committed
│   └── credit_data.db.enc                # encrypted customer bureau DB — gitignored
├── notebooks/
│   └── scrub_analysis.ipynb              # bureau scrub comparison analysis
├── src/
│   ├── ingest.py               # Ingestion pipeline: load → chunk → embed → store
│   ├── encrypt_kb.py           # Encrypt/decrypt sensitive KB files
│   ├── rag_pipeline.py         # RAG query pipeline: retrieve → prompt → generate
│   ├── db.py                   # Encrypted SQLite load/save + query helpers
│   ├── score_drivers.py        # Creates data/score_drivers.db (reference data)
│   ├── load_scrub_data.py      # ETL: scrub CSV → encrypted credit_data.db.enc
│   └── generate_kb_drivers.py  # Generates 09_score_driver_reference.md from DB
├── app.py                 # Streamlit chat UI
├── requirements.txt       # Python dependencies
└── .gitignore
```

## Setup & Running

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- Models pulled: `ollama pull mistral` and `ollama pull llama3.2:3b`

### Installation
```bash
# Clone the repo
git clone git@github.com:ayushigupta-29/credit-chatbot.git
cd credit-chatbot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Build the reference DB and knowledge base
```bash
# 1. Create score_drivers.db (reference data — run once or when drivers change)
python src/score_drivers.py

# 2. Generate score driver KB doc from the reference DB
python src/generate_kb_drivers.py

# 3. Ingest all KB docs into ChromaDB (re-run when any KB file changes)
python src/ingest.py
```

### Load customer bureau data (internal only)
```bash
# ETL from scrub CSV → encrypted credit_data.db.enc
# Requires: notebooks/scrub_comparison_master.csv + KB_ENCRYPTION_KEY in .env
python src/load_scrub_data.py
```

### Run the app
```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

### Encrypted knowledge base files
Sensitive KB docs (07, 08, data dictionary) are encrypted. To work with them:
```bash
# Decrypt for editing (requires KB_ENCRYPTION_KEY in .env)
python src/encrypt_kb.py decrypt

# Re-encrypt after editing
python src/encrypt_kb.py encrypt
```

---

## Roadmap
- [x] RAG-based credit education chatbot
- [x] Streamlit web UI with streaming responses
- [x] Source attribution per answer
- [x] Model toggle (LLaMA 3.2 3B fast / Mistral 7B quality)
- [x] Encrypted knowledge base for sensitive docs
- [x] Bureau scrub comparison analysis notebook
- [x] Phone login + consent-gated personalised answers
- [x] Encrypted customer bureau DB (in-memory at runtime)
- [x] Score driver reference system with approval workflow
- [ ] KB docs 07 + 08 (score patterns + bureau parameters)
- [ ] Score driver thresholds (quantified impact ranges per driver)
- [ ] Fine-tuning dataset from scrub analysis
- [ ] Fine-tune LLaMA 3.2 3B with QLoRA via MLX (local, Apple Silicon)
- [ ] Evaluation framework (RAGAS)
