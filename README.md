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
- Runs entirely locally — no API costs, no data leaving your machine

## How it works (RAG Architecture)
```
User Question
     ↓
[Embedding model converts question to vector]
     ↓
[ChromaDB finds most semantically similar chunks from knowledge base]
     ↓
[Mistral 7B receives: system prompt + relevant chunks + question]
     ↓
Answer (streamed live) + Sources shown
```

## Knowledge Base
The chatbot answers from 6 curated documents covering:
- Credit score fundamentals (CIBIL, Experian, CRIF, Equifax)
- How to improve your credit score
- Credit cards and utilisation
- Loans, EMIs, interest rates, and key terms
- Credit reports and how to dispute errors
- Frequently asked questions

## Tech Stack
| Layer | Tool |
|---|---|
| LLM | Mistral 7B via Ollama (runs locally) |
| Embeddings | sentence-transformers / all-MiniLM-L6-v2 |
| Vector DB | ChromaDB (local) |
| Orchestration | LangChain |
| UI | Streamlit |

## Project Structure
```
credit-chatbot/
├── knowledge_base/
│   ├── 01_credit_score_fundamentals.md
│   ├── 02_improving_credit_score.md
│   ├── 03_credit_cards.md
│   ├── 04_loans_and_credit.md
│   ├── 05_credit_reports.md
│   └── 06_faqs.md
├── src/
│   ├── ingest.py          # Ingestion pipeline: load → chunk → embed → store
│   └── rag_pipeline.py    # RAG query pipeline: retrieve → prompt → generate
├── app.py                 # Streamlit chat UI
├── requirements.txt       # Python dependencies
└── .gitignore
```

## Setup & Running

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- Mistral 7B pulled: `ollama pull mistral`

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

### Build the knowledge base
```bash
# Ingest documents into ChromaDB (run once, re-run when KB is updated)
python src/ingest.py
```

### Run the app
```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## Roadmap
- [x] RAG-based credit education chatbot
- [x] Streamlit web UI with streaming responses
- [x] Source attribution per answer
- [ ] Fine-tuning on credit Q&A dataset
- [ ] Evaluation framework (RAGAS)
- [ ] Expanded knowledge base
