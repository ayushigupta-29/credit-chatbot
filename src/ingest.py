"""
Ingestion Pipeline — credit-chatbot
------------------------------------
Reads knowledge base documents, splits them into chunks,
converts chunks to embeddings, and stores in ChromaDB.

Run this script once to populate the vector database.
Re-run it any time you update the knowledge base files.
"""

import os
import shutil
import tempfile

from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH     = os.path.join(BASE_DIR, "knowledge_base")
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

# ── Encryption key ─────────────────────────────────────────────────────────────
load_dotenv(os.path.join(BASE_DIR, ".env"))
_KB_KEY = os.environ.get("KB_ENCRYPTION_KEY")

# ── Embedding model ────────────────────────────────────────────────────────────
# all-MiniLM-L6-v2: a small (90MB), fast, high-quality sentence embedding model.
# It converts text into 384-dimensional vectors.
# Downloaded automatically from HuggingFace on first run, cached locally after.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Chunking settings ──────────────────────────────────────────────────────────
CHUNK_SIZE    = 500   # maximum characters per chunk
CHUNK_OVERLAP = 100   # characters shared between consecutive chunks


def load_encrypted_doc(enc_path: str) -> Document:
    """
    Decrypt a .enc knowledge base file in memory and return a LangChain Document.
    The decrypted content is never written to disk.
    """
    from cryptography.fernet import Fernet
    if not _KB_KEY:
        raise RuntimeError("KB_ENCRYPTION_KEY missing from .env — cannot decrypt encrypted KB files.")
    f = Fernet(_KB_KEY.encode())
    decrypted = f.decrypt(open(enc_path, "rb").read()).decode("utf-8")
    return Document(page_content=decrypted, metadata={"source": enc_path.replace(".enc", "")})


def load_documents():
    """
    Load all knowledge base files:
    - Plain .md files → loaded directly
    - .md.enc and .pdf.enc files → decrypted in memory using KB_ENCRYPTION_KEY
    """
    print(f"\n[1/4] Loading documents from: {KB_PATH}")

    # Load plain markdown files
    loader = DirectoryLoader(
        KB_PATH,
        glob="*.md",            # top-level .md files only (not encrypted)
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    documents = loader.load()

    # Load encrypted .enc files (markdown and PDF text)
    for root, _, files in os.walk(KB_PATH):
        for fname in files:
            if fname.endswith(".enc"):
                enc_path = os.path.join(root, fname)
                try:
                    doc = load_encrypted_doc(enc_path)
                    documents.append(doc)
                    print(f"      Decrypted: {fname}")
                except Exception as e:
                    print(f"      WARN: Could not decrypt {fname}: {e}")

    print(f"      Loaded {len(documents)} documents total ({sum(1 for d in documents if '.enc' not in d.metadata.get('source',''))} plain + {sum(1 for d in documents if '.enc' in d.metadata.get('source',''))} encrypted)")
    return documents


def split_documents(documents):
    """
    Split documents into smaller chunks using RecursiveCharacterTextSplitter.

    'Recursive' means it tries to split on natural boundaries first:
    paragraphs (\n\n), then sentences (\n), then words ( ), then characters.
    This preserves meaning better than blindly cutting at character count.
    """
    print(f"\n[2/4] Splitting documents into chunks...")
    print(f"      Chunk size: {CHUNK_SIZE} chars | Overlap: {CHUNK_OVERLAP} chars")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    chunks = splitter.split_documents(documents)
    print(f"      Created {len(chunks)} chunks from {len(documents)} documents")
    return chunks


def embed_and_store(chunks):
    """
    Convert each chunk into an embedding vector and store in ChromaDB.

    Steps:
    1. Load the sentence-transformer embedding model
    2. Clear any existing ChromaDB (so we always have a fresh, consistent state)
    3. For each chunk: generate embedding → store (text + embedding + metadata) in ChromaDB
    """
    print(f"\n[3/4] Loading embedding model: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # Clear existing DB so updates to knowledge base are always reflected cleanly
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
        print(f"      Cleared existing ChromaDB at {CHROMA_PATH}")

    print(f"\n[4/4] Generating embeddings and storing in ChromaDB...")
    print(f"      This may take a minute on first run...")

    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH,
    )

    print(f"      Stored {len(chunks)} chunks in ChromaDB at {CHROMA_PATH}")
    return db


def verify_store(db):
    """
    Quick sanity check: run a test query against the vector store
    to confirm retrieval is working before we build the chatbot on top.
    """
    print(f"\n── Verification ──────────────────────────────────────────")
    test_query = "What is a good credit score in India?"
    print(f"Test query: '{test_query}'")

    results = db.similarity_search(test_query, k=3)  # return top 3 matching chunks
    print(f"Top {len(results)} matching chunks:\n")
    for i, doc in enumerate(results, 1):
        source = os.path.basename(doc.metadata.get("source", "unknown"))
        preview = doc.page_content[:200].replace("\n", " ")
        print(f"  [{i}] Source: {source}")
        print(f"       Preview: {preview}...")
        print()


if __name__ == "__main__":
    print("=" * 60)
    print("  Credit Chatbot — Ingestion Pipeline")
    print("=" * 60)

    documents = load_documents()
    chunks    = split_documents(documents)
    db        = embed_and_store(chunks)
    verify_store(db)

    print("=" * 60)
    print("  Ingestion complete. ChromaDB is ready.")
    print("=" * 60)
