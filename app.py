"""
Credit Chatbot — Streamlit Web UI
-----------------------------------
Run with:  streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from rag_pipeline import load_vector_store, ask_stream

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Credit Chatbot",
    page_icon="💳",
    layout="centered",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Blue background for user chat messages */
[data-testid="stChatMessage"][style*="row-reverse"] {
    background-color: rgba(37, 99, 235, 0.12) !important;
    border-radius: 12px;
    padding: 4px 8px;
}

/* User avatar circle — target parent of the Material icon */
[data-testid="stChatMessage"][style*="row-reverse"] :has(> [data-testid="stIconMaterial"]) {
    background-color: #2563eb !important;
}
[data-testid="stChatMessage"][style*="row-reverse"] [data-testid="stIconMaterial"] {
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
EXAMPLES = [
    "What is a good credit score?",
    "How can I improve my CIBIL score?",
    "Does checking my score lower it?",
    "What is credit utilisation?",
    "What happens if I miss an EMI?",
]

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "auto_question" not in st.session_state:
    st.session_state.auto_question = ""

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💳 Credit Chatbot")
    st.markdown(
        "Ask me anything about **credit scores**, **credit cards**, "
        "**loans**, and **credit reports** in India."
    )
    st.divider()

    model_choice = st.radio(
        "Mode",
        options=["llama3.2:3b", "mistral"],
        index=0,
        format_func=lambda x: "⚡ Quick Answer (LLaMA 3.2 3B)" if x == "llama3.2:3b" else "🧠 Deep Thinking (Mistral 7B)",
        help="Quick Answer is faster. Deep Thinking is slower but more thorough.",
    )

    st.divider()
    st.markdown("**Example questions:**")

    # Clicking an example auto-submits it as a question (like ChatGPT)
    for example in EXAMPLES:
        if st.button(f"💬 {example}", key=f"ex_{example[:30]}", use_container_width=True):
            st.session_state.auto_question = example
            st.rerun()

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.session_state.auto_question = ""
        st.rerun()
    st.caption("Powered by Ollama + RAG")

# ── Load vector store ──────────────────────────────────────────────────────────
@st.cache_resource
def get_vector_store():
    with st.spinner("Loading knowledge base..."):
        return load_vector_store()

db = get_vector_store()

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("💳 Credit Chatbot")
st.caption("Your credit education assistant — ask me anything about credit in India.")
st.divider()

# ── Chat messages ──────────────────────────────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("📄 Sources used", expanded=False):
                for s in message["sources"]:
                    st.caption(f"**{s['file']}** — {s['preview']}")

# Placeholder for streaming — sits above the sticky input bar
stream_slot = st.empty()

# ── Input — st.chat_input is natively sticky at the bottom ────────────────────
typed_question = st.chat_input("Ask a question about credit...")

# Resolve question source: typed input takes priority, else auto from sidebar
question = typed_question or st.session_state.auto_question or None
if st.session_state.auto_question:
    st.session_state.auto_question = ""   # clear after consuming

# ── Handle question ────────────────────────────────────────────────────────────
if question:
    words = question.strip().split()
    if len(words) < 2:
        st.warning("Please enter at least 2 words.")
    else:
        st.session_state.messages.append({"role": "user", "content": question})

        with stream_slot.container():
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                collected_tokens = []
                sources = []

                def token_generator():
                    for chunk in ask_stream(db, question, st.session_state.chat_history, model=model_choice):
                        if isinstance(chunk, list):
                            sources.extend(chunk)
                        else:
                            collected_tokens.append(chunk)
                            yield chunk

                st.write_stream(token_generator())

                if sources:
                    with st.expander("📄 Sources used", expanded=False):
                        for s in sources:
                            st.caption(f"**{s['file']}** — {s['preview']}")

        full_answer = "".join(collected_tokens)
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_answer,
            "sources": sources,
        })
        st.session_state.chat_history.append({
            "user": question,
            "assistant": full_answer,
        })
        st.rerun()

# ── Auto-focus: typing anywhere goes to the chat input (like ChatGPT) ─────────
# Only on initial load — no MutationObserver so sidebar button clicks are
# never intercepted.
components.html("""
<script>
    const doc = window.parent.document;

    function focusChatInput() {
        const input = doc.querySelector('textarea[data-testid="stChatInputTextArea"]');
        if (input) input.focus();
    }

    // Focus once on load
    setTimeout(focusChatInput, 400);

    // Redirect bare keypresses to the chat input — but NEVER if a button,
    // link, or interactive element is focused or being clicked
    doc.addEventListener('keydown', function(e) {
        const active = doc.activeElement;
        const tag = active ? active.tagName : '';
        const isInteractive = ['INPUT', 'TEXTAREA', 'BUTTON', 'A', 'SELECT'].includes(tag);
        if (!isInteractive && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
            focusChatInput();
        }
    });
</script>
""", height=0)
