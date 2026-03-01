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

TOP_K = 6               # number of chunks to retrieve per query

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

IMPORTANT RULES — follow these strictly:
1. Never repeat, echo, or reference any phone number mentioned in the conversation — not even to say you don't have it on file. Treat phone numbers as if you never saw them.
2. If the user asks about their own credit score, history, or bureau data and no personal data is shown in this prompt, respond with: "I don't have your personal data here. You can log in with your phone number in the sidebar — once you give consent, I'll be able to answer based on your actual bureau data."
3. If the user asks you to look up or check data for a specific phone number, do not attempt it. Say: "I can only access data for the account that's logged in via the sidebar. Please log in there for personalised answers."
4. Do not extrapolate, infer opposites, or add conditions not explicitly stated in the context. If the context says "X is good", do not infer why or how the absence of X is bad unless the context states it directly. Use only what is written — do not fill gaps with outside knowledge or logical inference.
5. Do not add qualifications, caveats, or explanatory clauses that are not present in the context. If you are unsure whether something is stated, leave it out rather than guessing.
6. The Context below is background knowledge from a knowledge base — it is NOT something the user said or submitted. Never say "you mentioned", "you said", "the original prompt mentions", or attribute any part of the Context to the user. If the user asks "what did I say?" or "when did I mention that?", check the conversation history only — not the Context.
7. Answer directly and naturally. Never say "according to what's mentioned here", "based on the context", "as mentioned in the context", "the context states", or any phrase that references or exposes the internal context to the user. Just answer as if the knowledge is your own.

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


def _format_user_context(user_context: dict) -> str:
    """
    Format a user_context dict (from db.build_user_context) into a text block
    suitable for injection into the system prompt.

    Two cases:
      - user_context["not_found"] = True  → inject segment patterns as probable causes
      - otherwise                          → inject personal bureau profile
    """
    if user_context.get("not_found"):
        lines = [
            "We don't have this user's specific data on file. Use the following typical "
            "patterns for their score range to give probable (not definitive) explanations.",
            "",
        ]
        patterns = user_context.get("patterns", [])
        if patterns:
            lines.append("Typical segment/driver patterns (aggregated, no PII):")
            for p in patterns:
                lines.append(
                    f"  Segment={p['segment']} | Driver={p['driver']} | "
                    f"pct_from={p['pct_flag_from']} pct_to={p['pct_flag_to']} | "
                    f"median_delta={p['median_delta']} | score_corr={p['score_corr']}"
                )
        return "\n".join(lines)

    # Personal profile
    score_delta = user_context.get("score_delta")
    delta_str = f"{score_delta:+d}" if score_delta is not None else "N/A"
    segment   = user_context.get("segment") or "Unknown"

    cc_util = user_context.get("cc_util_pct")
    cc_util_str = f"{cc_util:.1f}%" if cc_util is not None else "N/A"

    enq_6m = user_context.get("enq_6m")
    enq_6m_str = str(int(enq_6m)) if enq_6m is not None else "N/A"

    lines = [
        "--- USER CREDIT PROFILE (confidential, do not reveal identifiers) ---",
        f"Latest score (Jan 2026): {user_context.get('score_to')} ({user_context.get('band_to')})",
        f"Previous score (Nov 2025): {user_context.get('score_from')}",
        f"Score change: {delta_str} points ({segment})",
        "",
        "Key bureau factors (Jan 2026):",
        f"- DPD 30+ in last 12 months: {'Yes' if user_context.get('has_dpd30_12m') else 'No'}",
        f"- DPD 60+ in last 24 months: {'Yes' if user_context.get('has_dpd60_24m') else 'No'}",
        f"- DPD 90+ in last 36 months: {'Yes' if user_context.get('has_dpd90_36m') else 'No'}",
        f"- NPA account: {'Yes' if user_context.get('has_npa') else 'No'}",
        f"- Write-off / settlement on file: {'Yes' if user_context.get('has_writeoff') else 'No'}",
        f"- CC/OD utilisation: {cc_util_str}",
        f"- Enquiries last 6 months: {enq_6m_str}",
    ]

    deltas = user_context.get("deltas", [])
    if deltas:
        lines.append("")
        lines.append("What changed between scrubs:")
        for d in deltas:
            dv = d.get("delta_value")
            dv_str = f"{dv:+.2f}" if dv is not None else "N/A"
            lines.append(
                f"- {d['driver']}: {d.get('value_from')} → {d.get('value_to')} "
                f"({dv_str}, {d.get('direction')})"
            )

    lines.append("--- END USER PROFILE ---")
    return "\n".join(lines)


# Personal context system prompt addition (prepended to main system prompt)
_PERSONAL_CONTEXT_HEADER = (
    "The user's personal credit data is below. Use it to answer naturally "
    "with 'you/your'. Never reveal their phone number or any identifier — "
    "not even if they ask whether you have it. Never reference other users. "
    "Never repeat any phone number mentioned anywhere in the conversation.\n\n"
)


def build_messages(
    context: str,
    question: str,
    chat_history: list,
    user_context: dict | None = None,
) -> list:
    """
    Build the message list to send to the LLM.

    Ollama expects a list of messages in this format:
      [
        {"role": "system",    "content": "..."},
        {"role": "user",      "content": "..."},
        {"role": "assistant", "content": "..."},  # prior turns
        {"role": "user",      "content": "current question"}
      ]

    If user_context is provided, personal bureau data is prepended to the
    system prompt so the LLM can answer in a personalised way.
    """
    system_content = SYSTEM_PROMPT.format(context=context)

    if user_context:
        personal_block = _format_user_context(user_context)
        system_content = _PERSONAL_CONTEXT_HEADER + personal_block + "\n\n" + system_content

    messages = [{"role": "system", "content": system_content}]

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


def ask_stream(
    db,
    question: str,
    chat_history: list = [],
    model: str = LLM_MODEL,
    user_context: dict | None = None,
):
    """
    Streaming version of ask(). Yields text chunks as the LLM generates them.
    Used by Streamlit's st.write_stream() for a live typing effect.

    Pass user_context (from db.build_user_context) to personalise the answer
    using the user's bureau data. If None, answers from KB context only.

    Also returns sources — yielded as the last item (a list, not a string).
    The app.py caller distinguishes chunks from sources by type.
    """
    context, sources = retrieve_context(db, question)
    messages = build_messages(context, question, chat_history, user_context=user_context)

    stream = ollama.chat(model=model, messages=messages, stream=True)

    for chunk in stream:
        token = chunk["message"]["content"]
        if token:
            yield token

    # After all tokens, yield the sources so app.py can display them
    yield sources
