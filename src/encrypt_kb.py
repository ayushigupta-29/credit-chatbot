"""
KB Encryption Utility
----------------------
Encrypts sensitive knowledge base files (markdown, PDF) using Fernet
symmetric encryption (AES-128-CBC). Encrypted files get a .enc extension
and are safe to commit to a public repo — unreadable without the key.

Your key lives in .env (already gitignored). Never share it.

Usage:
    python src/encrypt_kb.py encrypt   # encrypt all pending files
    python src/encrypt_kb.py decrypt   # decrypt all .enc files (for editing)
    python src/encrypt_kb.py genkey    # generate a fresh key (first-time setup)
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"


def get_key():
    """Load the encryption key from .env."""
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)
    key = os.environ.get("KB_ENCRYPTION_KEY")
    if not key:
        print("ERROR: KB_ENCRYPTION_KEY not found in .env")
        print("Run:  python src/encrypt_kb.py genkey")
        sys.exit(1)
    return key.encode()


def generate_key():
    """Generate a new Fernet key and save it to .env."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()

    # Append to .env (or create it)
    env_content = ""
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text()

    if "KB_ENCRYPTION_KEY" in env_content:
        print("KB_ENCRYPTION_KEY already exists in .env — not overwriting.")
        print("Delete it manually if you want to regenerate.")
        return

    with open(ENV_FILE, "a") as f:
        f.write(f"\nKB_ENCRYPTION_KEY={key}\n")

    print(f"Key generated and saved to .env")
    print(f"IMPORTANT: Back up this key. Without it you cannot decrypt your files.")
    print(f"Key: {key}")


def encrypt_file(path: Path, key: bytes):
    """Encrypt a plaintext file → .enc file, then delete the original."""
    from cryptography.fernet import Fernet
    f = Fernet(key)
    data = path.read_bytes()
    encrypted = f.encrypt(data)
    enc_path = path.with_suffix(path.suffix + ".enc")
    enc_path.write_bytes(encrypted)
    path.unlink()  # remove plaintext
    print(f"  Encrypted: {path.name} → {enc_path.name}")
    return enc_path


def decrypt_file(path: Path, key: bytes):
    """Decrypt a .enc file → original file."""
    from cryptography.fernet import Fernet
    f = Fernet(key)
    data = path.read_bytes()
    decrypted = f.decrypt(data)
    # Remove the .enc suffix to get original path
    original_path = path.with_suffix("")
    original_path.write_bytes(decrypted)
    print(f"  Decrypted: {path.name} → {original_path.name}")
    return original_path


def decrypt_to_bytes(path: Path, key: bytes) -> bytes:
    """Decrypt a .enc file and return bytes (used by ingest.py at runtime)."""
    from cryptography.fernet import Fernet
    f = Fernet(key)
    return f.decrypt(path.read_bytes())


# Files to encrypt (relative to project root)
ENCRYPT_TARGETS = [
    "knowledge_base/08_bureau_parameters.md",
    "knowledge_base/07_score_patterns.md",
    "knowledge_base/data_dictionary/experian_scrub_dictionary_jan2026.pdf",
]


def run_encrypt():
    key = get_key()
    encrypted_count = 0
    for rel_path in ENCRYPT_TARGETS:
        path = BASE_DIR / rel_path
        if path.exists():
            encrypt_file(path, key)
            encrypted_count += 1
        else:
            enc_path = Path(str(path) + ".enc")
            if enc_path.exists():
                print(f"  Already encrypted: {enc_path.name}")
            else:
                print(f"  Not found (skip): {rel_path}")
    print(f"\nDone. {encrypted_count} file(s) encrypted.")


def run_decrypt():
    key = get_key()
    decrypted_count = 0
    for rel_path in ENCRYPT_TARGETS:
        enc_path = BASE_DIR / (rel_path + ".enc")
        if enc_path.exists():
            decrypt_file(enc_path, key)
            decrypted_count += 1
        else:
            print(f"  Not found (skip): {enc_path.name}")
    print(f"\nDone. {decrypted_count} file(s) decrypted.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "genkey":
        generate_key()
    elif cmd == "encrypt":
        run_encrypt()
    elif cmd == "decrypt":
        run_decrypt()
    else:
        print(__doc__)
