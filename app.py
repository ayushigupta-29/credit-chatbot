"""
Credit Chatbot — Streamlit Web UI
-----------------------------------
Run with:  streamlit run app.py
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from rag_pipeline import load_vector_store, ask_stream, LLM_MODEL

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Credit Chatbot",
    page_icon="💳",
    layout="centered",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💳 Credit Chatbot")
    st.markdown(
        "Ask me anything about **credit scores**, **credit cards**, "
        "**loans**, and **credit reports** in India."
    )
    st.divider()

    # Model selector — switch without touching code
    # Changes take effect on the next message sent
    model_choice = st.radio(
        "Model",
        options=["llama3.2:3b", "mistral"],
        index=0,
        help="LLaMA 3.2 3B is faster. Mistral 7B is slower but higher quality.",
    )
    st.caption("⚡ Fast" if model_choice == "llama3.2:3b" else "🎯 Quality")

    st.divider()
    st.markdown("**Example questions:**")
    st.markdown("- What is a good credit score?")
    st.markdown("- How can I improve my CIBIL score?")
    st.markdown("- Does checking my score lower it?")
    st.markdown("- What is credit utilisation?")
    st.markdown("- What happens if I miss an EMI?")
    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()
    st.caption(f"Powered by {model_choice} + RAG")

# ── Load vector store (cached — runs once, not on every message) ───────────────
# st.cache_resource tells Streamlit: "load this once and reuse it across
# all user sessions". Without this, the embedding model would reload on
# every single message — very slow.
@st.cache_resource
def get_vector_store():
    with st.spinner("Loading knowledge base..."):
        return load_vector_store()

db = get_vector_store()

# ── Session state — persists across reruns within a session ───────────────────
# Streamlit re-runs the entire script on every user interaction.
# st.session_state is how you keep data (like chat history) alive between reruns.
if "messages" not in st.session_state:
    st.session_state.messages = []       # for displaying in the UI

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # for passing context to the LLM

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("💳 Credit Chatbot")
st.caption("Your credit education assistant — ask me anything about credit in India.")
st.divider()

# ── Display existing chat messages ─────────────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Show sources if they exist on this message
        if message.get("sources"):
            with st.expander("📄 Sources used", expanded=False):
                for s in message["sources"]:
                    st.caption(f"**{s['file']}** — {s['preview']}")

# ── Chat input ─────────────────────────────────────────────────────────────────
if question := st.chat_input("Ask a question about credit..."):

    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Generate and stream the assistant response
    with st.chat_message("assistant"):
        collected_tokens = []
        sources = []

        def token_generator():
            """
            Wraps ask_stream() to separate text tokens from the sources object.
            Streamlit's st.write_stream() expects a generator of strings only.
            """
            for chunk in ask_stream(db, question, st.session_state.chat_history, model=model_choice):
                if isinstance(chunk, list):
                    # This is the sources payload yielded at the end
                    sources.extend(chunk)
                else:
                    collected_tokens.append(chunk)
                    yield chunk

        # st.write_stream displays tokens as they arrive — live typing effect
        st.write_stream(token_generator())

        # Show sources below the answer
        if sources:
            with st.expander("📄 Sources used", expanded=False):
                for s in sources:
                    st.caption(f"**{s['file']}** — {s['preview']}")

    # Assemble the full answer from collected tokens
    full_answer = "".join(collected_tokens)

    # Save to session state for display persistence
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_answer,
        "sources": sources,
    })

    # Save to chat history for LLM context (follow-up questions)
    st.session_state.chat_history.append({
        "user": question,
        "assistant": full_answer,
    })
