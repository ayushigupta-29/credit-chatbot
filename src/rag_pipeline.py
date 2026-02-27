"""
RAG Query Pipeline — credit-chatbot
-------------------------------------
Handles the full retrieval-augmented generation flow:
  1. Load ChromaDB vector store
  2. Convert user question to embedding
  3. Retrieve top-k most relevant chunks
  4. Build a prompt (system + context + question)
  5. Send to LLM via Ollama
  6. Return answer + source documents

This module is imported by app.py (the Streamlit UI).
"""

import os
import ollama
import warnings
warnings.filterwarnings("ignore")  # suppress LangChain deprecation noise

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

# ── Model settings ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Toggle between models:
#   "llama3.2:3b"  — fast, good for development and testing (~4-5s per response)
#   "mistral"      — slower, higher quality for demos and production (~12-15s per response)
LLM_MODEL = "llama3.2:3b"

TOP_K = 4               # number of chunks to retrieve per query

# ── System Prompt ──────────────────────────────────────────────────────────────
# This is the most important piece of prompt engineering in the whole project.
# It tells Mistral exactly how to behave before it sees any user question.
# Rules we're setting:
#   - Only answer from the provided context (prevents hallucination)
#   - If the answer isn't in the context, say so honestly
#   - Stay focused on credit topics
#   - Be concise, clear, and helpful
SYSTEM_PROMPT = """You are a knowledgeable and friendly credit education assistant. \
Your job is to help users in India understand credit scores, credit cards, loans, \
and related financial concepts.

Answer the user's question using ONLY the context provided below. \
Do not use any outside knowledge. If the answer is not clearly present in the context, \
say: "I don't have enough information on that in my knowledge base. \
You can check your credit report on Bachatt or speak to a financial advisor."

Keep your answers clear, concise, and easy to understand. \
Avoid jargon where possible — if you must use a financial term, briefly explain it. \
Do not give personalised financial advice; provide education and general guidance only.

Context:
{context}"""


def load_vector_store():
    """
    Load the ChromaDB vector store from disk.
    Called once when the Streamlit app starts — cached so it doesn't reload
    on every user message.
    """
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
    )
    return db


def retrieve_context(db, question: str) -> tuple[str, list[dict]]:
    """
    Search ChromaDB for the top-k chunks most semantically similar to the question.

    Returns:
      - context_text: all chunks joined into a single string to inject into the prompt
      - sources: list of dicts with source filename and preview, shown in the UI
    """
    results = db.similarity_search(question, k=TOP_K)

    # Join all retrieved chunks into one context block
    context_text = "\n\n---\n\n".join([doc.page_content for doc in results])

    # Build a sources list for display in the UI
    sources = []
    seen = set()
    for doc in results:
        source = os.path.basename(doc.metadata.get("source", "unknown"))
        if source not in seen:
            seen.add(source)
            sources.append({
                "file": source,
                "preview": doc.page_content[:150].replace("\n", " ") + "..."
            })

    return context_text, sources


def build_messages(context: str, question: str, chat_history: list) -> list:
    """
    Build the message list to send to Mistral.

    Ollama expects a list of messages in this format:
      [
        {"role": "system",    "content": "..."},
        {"role": "user",      "content": "..."},
        {"role": "assistant", "content": "..."},  # prior turns
        {"role": "user",      "content": "current question"}
      ]

    Including chat_history allows the model to understand follow-up questions
    like "tell me more about that" or "what about credit cards?"
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)}
    ]

    # Add previous conversation turns (up to last 6 to avoid hitting context limits)
    for turn in chat_history[-6:]:
        messages.append({"role": "user",      "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})

    # Add the current question
    messages.append({"role": "user", "content": question})

    return messages


def ask(db, question: str, chat_history: list = []) -> tuple[str, list[dict]]:
    """
    Main entry point. Given a question, return a complete answer and sources.
    Used when streaming is not needed.
    """
    context, sources = retrieve_context(db, question)
    messages = build_messages(context, question, chat_history)

    response = ollama.chat(model=LLM_MODEL, messages=messages)
    answer = response["message"]["content"]

    return answer, sources


def ask_stream(db, question: str, chat_history: list = [], model: str = LLM_MODEL):
    """
    Streaming version of ask(). Yields text chunks as Mistral generates them.
    Used by Streamlit's st.write_stream() for a live typing effect.

    Also returns sources — yielded as the last item (a list, not a string).
    The app.py caller distinguishes chunks from sources by type.
    """
    context, sources = retrieve_context(db, question)
    messages = build_messages(context, question, chat_history)

    stream = ollama.chat(model=model, messages=messages, stream=True)

    for chunk in stream:
        token = chunk["message"]["content"]
        if token:
            yield token

    # After all tokens, yield the sources so app.py can display them
    yield sources
