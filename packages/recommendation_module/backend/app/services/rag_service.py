import hashlib
import json
from pathlib import Path

import chromadb
from fastembed import TextEmbedding
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
RAG_STORE_DIR = BASE_DIR / "rag_store"
RAG_CACHE_DIR = BASE_DIR / "rag_cache"
RAG_CACHE_FILE = RAG_CACHE_DIR / "indexed_files.json"
MODEL_CACHE_DIR = BASE_DIR / "model_cache"

RAG_STORE_DIR.mkdir(parents=True, exist_ok=True)
RAG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)


_embedding_model = None
_chroma_client = None
_collection = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = TextEmbedding(
            "sentence-transformers/all-MiniLM-L6-v2",
            cache_dir=str(MODEL_CACHE_DIR),
        )
    return _embedding_model


def get_chroma_collection():
    global _chroma_client, _collection

    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=str(RAG_STORE_DIR))
        _collection = _chroma_client.get_or_create_collection(name="knowledge_chunks")

    return _collection


def load_index_cache():
    if not RAG_CACHE_FILE.exists():
        return {}

    try:
        return json.loads(RAG_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_index_cache(data):
    RAG_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def compute_file_hash(file_path: Path):
    content = file_path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def read_text_file(file_path: Path):
    return file_path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_file(file_path: Path):
    reader = PdfReader(str(file_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages)


def read_document(file_path: Path):
    suffix = file_path.suffix.lower()

    if suffix in [".txt", ".md"]:
        return read_text_file(file_path)

    if suffix == ".pdf":
        return read_pdf_file(file_path)

    return ""


def chunk_text(text, chunk_size=1200, overlap=200):
    chunks = []
    start = 0
    text = text.strip()

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += max(chunk_size - overlap, 1)

    return chunks


def get_app_knowledge_paths(app_id):
    paths = [
        KNOWLEDGE_BASE_DIR / "common",
        KNOWLEDGE_BASE_DIR / "applications" / app_id,
    ]
    return [p for p in paths if p.exists()]


def list_documents_for_app(app_id):
    docs = []

    for base_path in get_app_knowledge_paths(app_id):
        for file_path in base_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in [".txt", ".md", ".pdf"]:
                docs.append(file_path)

    return docs


def build_chunk_id(app_id, file_path: Path, chunk_index: int):
    raw = f"{app_id}:{file_path.as_posix()}:{chunk_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def index_documents_for_app(app_id):
    collection = get_chroma_collection()
    model = get_embedding_model()
    cache = load_index_cache()

    files = list_documents_for_app(app_id)

    for file_path in files:
        file_hash = compute_file_hash(file_path)
        cache_key = f"{app_id}:{file_path.as_posix()}"

        if cache.get(cache_key) == file_hash:
            continue

        text = read_document(file_path)
        if not text.strip():
            continue

        chunks = chunk_text(text)

        chunk_ids = []
        chunk_texts = []
        metadatas = []

        for idx, chunk in enumerate(chunks):
            chunk_id = build_chunk_id(app_id, file_path, idx)
            chunk_ids.append(chunk_id)
            chunk_texts.append(chunk)
            metadatas.append(
                {
                    "application_id": app_id,
                    "source_file": str(file_path),
                    "chunk_index": idx,
                    "category": "application" if f"applications/{app_id}" in str(file_path).replace("\\", "/") else "common",
                }
            )

        embeddings = [emb.tolist() for emb in model.embed(chunk_texts)]

        try:
            existing = collection.get(ids=chunk_ids)
            existing_ids = set(existing.get("ids", []))
        except Exception:
            existing_ids = set()

        new_ids = []
        new_docs = []
        new_embeddings = []
        new_metadatas = []

        for i, cid in enumerate(chunk_ids):
            if cid not in existing_ids:
                new_ids.append(cid)
                new_docs.append(chunk_texts[i])
                new_embeddings.append(embeddings[i])
                new_metadatas.append(metadatas[i])

        if new_ids:
            collection.add(
                ids=new_ids,
                documents=new_docs,
                embeddings=new_embeddings,
                metadatas=new_metadatas,
            )

        cache[cache_key] = file_hash

    save_index_cache(cache)


def retrieve_relevant_chunks(app_id: str, question: str, top_k: int = 5):
    index_documents_for_app(app_id)

    collection = get_chroma_collection()
    total_docs = collection.count()
    if total_docs == 0:
        return []

    model = get_embedding_model()
    query_embedding = list(model.embed([question]))[0].tolist()

    n_app = min(top_k, total_docs)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_app,
        where={"application_id": app_id},
    )

    docs = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    retrieved = []
    for doc, meta in zip(docs, metadatas):
        retrieved.append(
            {
                "text": doc,
                "metadata": meta,
            }
        )

    # Also retrieve from common docs if app-specific docs are too few
    if len(retrieved) < top_k:
        n_extra = min(top_k - len(retrieved), total_docs)
        if n_extra > 0:
            extra_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_extra,
                where={"category": "common"},
            )

            extra_docs = extra_results.get("documents", [[]])[0]
            extra_metas = extra_results.get("metadatas", [[]])[0]

            for doc, meta in zip(extra_docs, extra_metas):
                retrieved.append(
                    {
                        "text": doc,
                        "metadata": meta,
                    }
                )

    return retrieved


def format_retrieved_knowledge(retrieved_chunks):
    if not retrieved_chunks:
        return "No relevant knowledge base documents were found."

    parts = []
    for idx, item in enumerate(retrieved_chunks[:2], start=1):
        source = item["metadata"].get("source_file", "unknown")
        text = item["text"].strip()[:800]
        parts.append(f"[Chunk {idx} | Source: {source}]\n{text}")

    return "\n\n".join(parts)