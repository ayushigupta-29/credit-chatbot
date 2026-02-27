# Credit Chatbot

An AI-powered chatbot that answers user queries related to credit — scores, loans, credit cards, and financial education.

## What it does
- Answers credit education questions using RAG (Retrieval Augmented Generation)
- Runs locally using Mistral 7B via Ollama
- Built with LangChain, ChromaDB, and Streamlit

## Tech Stack
- **LLM:** Mistral 7B (local, via Ollama)
- **Embeddings:** sentence-transformers
- **Vector DB:** ChromaDB
- **Orchestration:** LangChain
- **UI:** Streamlit

## Project Structure
```
credit-chatbot/
├── knowledge_base/     # Credit education documents
├── src/                # Core pipeline code
├── app.py              # Streamlit web UI
└── requirements.txt    # Python dependencies
```
