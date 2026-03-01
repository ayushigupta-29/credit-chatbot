"""
Credit Chatbot — Streamlit Web UI
-----------------------------------
Run with:  streamlit run app.py
"""

import uuid

import streamlit as st
import streamlit.components.v1 as components
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from rag_pipeline import load_vector_store, ask_stream
from db import load_db, save_db, get_user_snapshot, get_segment_patterns, save_consent, build_user_context

CONSENT_TEXT = (
    "I consent to Bachatt accessing my credit bureau data on file to provide "
    "personalised answers in this session."
)

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

/* User avatar — try all known Streamlit avatar testids */
[data-testid="stChatMessageAvatarUser"] {
    background-color: #2563eb !important;
}
[data-testid="stChatMessageAvatarUser"] [data-testid="stIconMaterial"] {
    color: white !important;
}

/* Fallback: avatar circle is parent of the face icon */
[data-testid="stChatMessage"] [style*="row-reverse"] :has(> [data-testid="stIconMaterial"]),
[data-testid="stChatMessage"][style*="row-reverse"] :has(> [data-testid="stIconMaterial"]) {
    background-color: #2563eb !important;
}
[data-testid="stChatMessage"] [style*="row-reverse"] [data-testid="stIconMaterial"],
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
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Personal data session state
if "user_phone" not in st.session_state:
    st.session_state.user_phone = None        # phone string once logged in
if "user_consented" not in st.session_state:
    st.session_state.user_consented = None    # None=not asked, True=yes, False=no
if "user_context" not in st.session_state:
    st.session_state.user_context = None      # dict from build_user_context, or None


# ── Consent dialog ─────────────────────────────────────────────────────────────
@st.dialog("Access your credit data")
def show_consent_dialog(phone: str):
    st.info(CONSENT_TEXT)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, I consent", type="primary", use_container_width=True):
            # Resolve user context before saving consent
            conn = load_db()
            ctx = build_user_context(phone, conn)
            if ctx is None:
                # User not in DB — inject segment patterns as probable causes
                patterns = get_segment_patterns(conn)
                ctx = {"not_found": True, "patterns": patterns}
            save_consent(phone, "credit_data_access", True, CONSENT_TEXT, st.session_state.session_id, conn)
            save_db(conn)
            conn.close()
            st.session_state.user_consented = True
            st.session_state.user_context = ctx
            st.rerun()
    with col2:
        if st.button("No, thanks", use_container_width=True):
            conn = load_db()
            save_consent(phone, "credit_data_access", False, CONSENT_TEXT, st.session_state.session_id, conn)
            save_db(conn)
            conn.close()
            st.session_state.user_consented = False
            st.session_state.user_context = None
            st.rerun()


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

    # ── Phone login ────────────────────────────────────────────────────────────
    st.markdown("**Your credit data**")
    if st.session_state.user_phone is None:
        phone_input = st.text_input(
            "Enter your phone number",
            placeholder="10-digit mobile number",
            key="phone_input",
            label_visibility="collapsed",
        )
        if st.button("Login", key="login_btn", use_container_width=True):
            phone = phone_input.strip() if phone_input else ""
            if phone:
                st.session_state.user_phone = phone
                st.session_state.user_consented = None  # trigger consent dialog
                st.rerun()
            else:
                st.warning("Please enter a phone number.")
    else:
        masked = "••••••" + st.session_state.user_phone[-4:]
        if st.session_state.user_consented is True:
            if st.session_state.user_context and st.session_state.user_context.get("not_found"):
                st.caption(f"Logged in: {masked} (data not on file)")
            else:
                st.caption(f"Logged in: {masked} (personalised)")
        elif st.session_state.user_consented is False:
            st.caption(f"Logged in: {masked} (general answers only)")
        else:
            st.caption(f"Logged in: {masked}")

        if st.button("Logout", key="logout_btn", use_container_width=True):
            st.session_state.user_phone = None
            st.session_state.user_consented = None
            st.session_state.user_context = None
            st.rerun()

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

# ── Show consent dialog when user just logged in ───────────────────────────────
if st.session_state.user_phone and st.session_state.user_consented is None:
    show_consent_dialog(st.session_state.user_phone)

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

        # Pass personal context only when user has consented
        active_user_context = (
            st.session_state.user_context
            if st.session_state.user_consented is True
            else None
        )

        with stream_slot.container():
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                collected_tokens = []
                sources = []

                def token_generator():
                    for chunk in ask_stream(
                        db,
                        question,
                        st.session_state.chat_history,
                        model=model_choice,
                        user_context=active_user_context,
                    ):
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
