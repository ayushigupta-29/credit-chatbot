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

/* Input box — blue focus ring only, nothing else touched */
[data-testid="stTextInput"] input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25) !important;
    outline: none !important;
}

/* Send button styling */
[data-testid="stFormSubmitButton"] button {
    border-radius: 8px !important;
    background-color: #2563eb !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
INPUT_KEY = "chat_input_text"
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

    for example in EXAMPLES:
        current_input = st.session_state.get(INPUT_KEY, "")
        is_selected = current_input == example
        label = f"✅ {example}" if is_selected else f"💬 {example}"
        if st.button(label, key=f"ex_{example[:30]}", use_container_width=True):
            st.session_state[INPUT_KEY] = "" if is_selected else example
            st.rerun()

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.session_state[INPUT_KEY] = ""
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

# ── Chat messages — always rendered ABOVE the input form ───────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("📄 Sources used", expanded=False):
                for s in message["sources"]:
                    st.caption(f"**{s['file']}** — {s['preview']}")

# Placeholder for streaming response — sits above the form in the DOM.
# During streaming, content fills this slot (above the input).
# After rerun, this is empty and the new messages appear in the loop above.
stream_slot = st.empty()

# ── Input form — always stays at the bottom ────────────────────────────────────
with st.form("chat_form", clear_on_submit=True):
    col1, col2 = st.columns([11, 1])
    with col1:
        question = st.text_input(
            "",
            key=INPUT_KEY,
            placeholder="Ask a question about credit...",
            label_visibility="collapsed",
        )
    with col2:
        submitted = st.form_submit_button("➤", use_container_width=True)

# ── Handle submission ──────────────────────────────────────────────────────────
if submitted and question:
    words = question.strip().split()
    if len(words) < 2:
        st.warning("Please type at least 2 words to ask a question.")
    else:
        st.session_state.messages.append({"role": "user", "content": question})

        # Stream into the slot ABOVE the form — form stays at the bottom throughout
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

        # Rerun — stream_slot clears, messages loop above form shows everything correctly
        st.rerun()

# ── Auto-focus: typing anywhere goes to the input (like ChatGPT) ───────────────
components.html("""
<script>
    const doc = window.parent.document;

    function focusInput() {
        const input = doc.querySelector('input[type="text"]');
        if (input && doc.activeElement !== input) input.focus();
    }

    setTimeout(focusInput, 300);

    new MutationObserver(() => setTimeout(focusInput, 100))
        .observe(doc.body, { childList: true, subtree: true });

    doc.addEventListener('keydown', function(e) {
        const active = doc.activeElement;
        const isTyping = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA');
        if (!isTyping && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
            const input = doc.querySelector('input[type="text"]');
            if (input) input.focus();
        }
    });
</script>
""", height=0)
