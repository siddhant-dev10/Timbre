"""Knowledge Ingestion and Hybrid Vector/Keyword Retrieval Service for Timbre.

Supports PDF, Markdown, Plain Text, CSV, JSON, and Statutory Scheme Catalogue ingestion.
Provides a versioned, deterministic multilingual embedding architecture (English, Devanagari Hindi, Hinglish)
using FastEmbed ONNX runtime on Apple Silicon, with a deterministic SHA-256 fallback.
Supports safe index rebuilding, cross-script query expansion, and source attribution.
"""
import csv
import hashlib
import io
import json
import logging
import math
import os
import re
import shutil
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.service_scheme import ServiceScheme

logger = logging.getLogger("timbre.knowledge")


class IncompatibleEmbeddingError(RuntimeError):
    """Raised when query vector space does not match indexed chunk vector space."""
    pass


# Cross-lingual civic terminology expansion dictionary
CIVIC_KEYWORD_EXPANSIONS: Dict[str, List[str]] = {
    "voter": ["मतदाता", "voter id", "epic", "form 6", "chunav", "election", "पहचान पत्र", "matdata"],
    "matdata": ["voter", "voter id", "form 6", "chunav", "मतदाता"],
    "मतदाता": ["voter", "voter id", "form 6", "epic", "election", "chunav", "पहचान पत्र"],
    "पहचान": ["id", "identity", "card", "epic", "pehchan"],
    "licence": ["license", "driving", "parivahan", "sarathi", "ll", "dl", "अनुज्ञप्ति", "लाइसेंस"],
    "license": ["licence", "driving", "parivahan", "sarathi", "ll", "dl", "अनुज्ञप्ति", "लाइसेंस"],
    "लाइसेंस": ["licence", "license", "driving", "parivahan", "sarathi", "ll"],
    "pan": ["pan card", "form 49a", "tax", "income tax", "पैन कार्ड"],
    "पैन": ["pan", "pan card", "form 49a", "income tax"],
    "kisan": ["farmer", "pm kisan", "samman nidhi", "agriculture", "किसान"],
    "किसान": ["kisan", "farmer", "pm kisan", "samman nidhi", "6000"],
    "ayushman": ["health", "hospital", "golden card", "pmjay", "insurance", "आयुष्मान"],
    "आयुष्मान": ["ayushman", "health", "hospital", "golden card", "pmjay", "5 lakh"],
    "scholarship": ["nsp", "student", "padhai", "post matric", "छात्रवृत्ति"],
    "छात्रवृत्ति": ["scholarship", "nsp", "student", "college", "fees"],
    "pension": ["old age", "ignoaps", "nsap", "vridhha", "bujurg", "पेंशन", "वृद्धावस्था"],
    "पेंशन": ["pension", "old age", "ignoaps", "nsap", "vridhha", "bujurg", "senior"],
    "वृद्धावस्था": ["pension", "old age", "ignoaps", "vridhha", "senior"],
    "sukanya": ["girl child", "beti", "daughter", "ssa", "सुकन्या समृद्धी"],
    "सुकन्या": ["sukanya", "girl child", "beti", "daughter", "post office"],
    "shram": ["e-shram", "labour", "worker", "uan", "श्रम"],
    "श्रम": ["shram", "eshram", "worker", "labour", "uan"],
    "disability": ["divyang", "udid", "swavlamban", "handicap", "दिव्यांग"],
    "दिव्यांग": ["disability", "udid", "swavlamban", "divyang", "card"],
}


COMMON_STOP_WORDS: Set[str] = {
    "the", "is", "in", "for", "a", "an", "and", "or", "of", "to", "what", "how", "can", "do", "does",
    "who", "which", "are", "under", "with", "from", "by", "as", "at", "it", "its", "all", "any",
    "ke", "liye", "ka", "ki", "ko", "me", "se", "hai", "kya", "kaise", "hoga", "kare", "karein",
    "aur", "ya", "hota", "hoti", "wale", "wali", "karo", "par", "bhi", "tha", "thi", "the",
    "का", "के", "की", "को", "में", "से", "है", "हैं", "क्या", "कैसे", "और", "या", "लिए", "हेतु", "पर", "द्वारा"
}


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class BaseEmbeddingProvider(ABC):
    """Abstract base class for deterministic embedding providers."""

    model_name: str
    version: str
    dimension: int

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of texts into normalized float vectors."""
        pass

    def embed_query(self, query: str) -> List[float]:
        """Embeds a single query string into a normalized float vector."""
        vecs = self.embed_texts([query])
        return vecs[0] if vecs else [0.0] * self.dimension


class FastEmbedMultilingualProvider(BaseEmbeddingProvider):
    """
    Genuine multilingual dense embedding model using FastEmbed ONNX runtime.
    Default model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions).
    High throughput, runs natively on Apple Silicon CPU/MPS without external APIs.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        version: str = "2.0.0",
        dimension: int = 384,
    ) -> None:
        self.model_name = model_name
        self.version = version
        self.dimension = dimension
        self._model = None

    def _check_system_resources(self) -> None:
        """Verifies disk space before initializing/downloading models."""
        try:
            total, used, free = shutil.disk_usage(os.path.expanduser("~"))
            free_mb = free / (1024 * 1024)
            if free_mb < 300:
                raise RuntimeError(
                    f"Insufficient disk space for embedding model. Required: 300MB, Available: {free_mb:.1f}MB"
                )
        except Exception as exc:
            logger.debug("Disk usage check: %s", exc)

    def _get_model(self):
        if self._model is None:
            self._check_system_resources()
            from fastembed import TextEmbedding
            logger.info("Initializing FastEmbed multilingual model '%s'...", self.model_name)
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        embeddings = list(model.embed(texts))
        result = []
        for vec in embeddings:
            arr = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(arr)
            if norm > 0:
                arr = arr / norm
            result.append(arr.tolist())
        return result


class DeterministicHashProvider(BaseEmbeddingProvider):
    """
    Deterministic subword and n-gram hash vector embedding using SHA-256.
    100% stable across process restarts, operating systems, and Python versions.
    Does not use Python's randomized hash().
    """

    def __init__(
        self,
        model_name: str = "deterministic-sha256-v2",
        version: str = "2.0.0",
        dimension: int = 256,
    ) -> None:
        self.model_name = model_name
        self.version = version
        self.dimension = dimension

    def _hash_token(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        # 32-bit unsigned integer from first 4 bytes of SHA-256
        return int.from_bytes(digest[:4], byteorder="little") % self.dimension

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        results = []
        for text in texts:
            vec = np.zeros(self.dimension, dtype=np.float32)
            clean = text.lower().strip()
            if not clean:
                results.append(vec.tolist())
                continue

            words = re.findall(r"[\w]+", clean)
            for w in words:
                h = self._hash_token(w)
                vec[h] += 1.0

            # Character 3-grams and 4-grams for morphological coverage
            for n in (3, 4):
                for i in range(len(clean) - n + 1):
                    sub = clean[i:i + n]
                    h = self._hash_token(sub)
                    vec[h] += 0.5

            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            results.append(vec.tolist())
        return results


# Global singleton cache for embedding providers
_provider_instance: Optional[BaseEmbeddingProvider] = None


def get_embedding_provider(provider_type: Optional[str] = None) -> BaseEmbeddingProvider:
    """Returns the configured embedding provider singleton."""
    global _provider_instance
    ptype = (provider_type or settings.EMBEDDING_PROVIDER).lower().strip()

    if _provider_instance is not None:
        if ptype == "deterministic_hash" and isinstance(_provider_instance, DeterministicHashProvider):
            return _provider_instance
        if ptype != "deterministic_hash" and isinstance(_provider_instance, FastEmbedMultilingualProvider):
            return _provider_instance

    if ptype == "deterministic_hash":
        logger.info("Using Deterministic SHA-256 embedding provider (dim=256)")
        _provider_instance = DeterministicHashProvider(
            model_name="deterministic-sha256-v2",
            version=settings.EMBEDDING_VERSION,
            dimension=256,
        )
    else:
        try:
            logger.info("Using FastEmbed multilingual provider: %s", settings.EMBEDDING_MODEL_NAME)
            _provider_instance = FastEmbedMultilingualProvider(
                model_name=settings.EMBEDDING_MODEL_NAME,
                version=settings.EMBEDDING_VERSION,
                dimension=settings.EMBEDDING_DIM,
            )
        except Exception as exc:
            logger.warning("FastEmbed unavailable (%s). Falling back to deterministic SHA-256 provider.", exc)
            _provider_instance = DeterministicHashProvider(
                model_name="deterministic-sha256-v2",
                version=settings.EMBEDDING_VERSION,
                dimension=256,
            )

    return _provider_instance


def _compute_embedding(text: str, dim: Optional[int] = None) -> List[float]:
    """Compatibility wrapper: computes embedding vector using the active provider."""
    provider = get_embedding_provider()
    return provider.embed_query(text)


# Canonical Devanagari Hindi aliases for statutory schemes
SCHEME_HINDI_ALIASES: Dict[str, str] = {
    "ECI-VOTER-FORM6": "मतदाता पहचान पत्र (वोटर आईडी कार्ड फॉर्म 6), निर्वाचन आयोग",
    "MORTH-PARIVAHAN-LL": "लर्नर ड्राइविंग लाइसेंस (चालन अनुज्ञप्ति), परिवहन सारथी पोर्टल",
    "ITD-PAN-FORM49A": "स्थायी खाता संख्या (पैन कार्ड फॉर्म 49A), आयकर विभाग",
    "AGRI-PMKISAN-DBT": "प्रधानमंत्री किसान सम्मान निधि योजना (पीएम-किसान 6000 रुपये)",
    "NHA-PMJAY-HEALTH": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना (पीएम-जय 5 लाख स्वास्थ्य बीमा गोल्डन कार्ड)",
    "MOE-NSP-POSTMATRIC": "राष्ट्रीय छात्रवृत्ति पोर्टल (पोस्ट-मैट्रिक छात्रवृत्ति योजना)",
    "RD-NSAP-IGNOAPS": "इंदिरा गांधी राष्ट्रीय वृद्धावस्था पेंशन योजना (बुजुर्ग मासिक पेंशन)",
    "DOP-SSA-GIRLCHILD": "सुकन्या समृद्धि योजना (बेटी बचाओ डाकघर बचत खाता)",
    "LE-ESHRAM-UAN": "ई-श्रम कार्ड (असंगठित कामगार श्रमिक यूएएन पंजीकरण)",
    "DEPWD-SWAVLAMBAN-UDID": "विशिष्ट दिव्यांगता पहचान पत्र (स्वावलंबन यूडीआईडी कार्ड)",
}


class KnowledgeService:
    """Manages document ingestion, chunking, indexing, and grounded retrieval."""

    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 100

    @property
    def provider(self) -> BaseEmbeddingProvider:
        return get_embedding_provider()

    def parse_pdf(self, content_bytes: bytes) -> List[Tuple[int, Optional[str], str]]:
        """Extracts text per page from PDF bytes using pypdf."""
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        pages_data = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                pages_data.append((idx + 1, f"Page {idx + 1}", text))
        return pages_data

    def parse_markdown(self, text: str) -> List[Tuple[Optional[int], Optional[str], str]]:
        """Parses Markdown splitting into sections based on headings."""
        lines = text.splitlines()
        sections = []
        current_heading = "Overview"
        current_lines = []

        for line in lines:
            if line.strip().startswith("#"):
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        sections.append((None, current_heading, content))
                    current_lines = []
                current_heading = line.strip().lstrip("#").strip()
            else:
                current_lines.append(line)

        if current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append((None, current_heading, content))

        return sections or [(None, "General", text.strip())]

    def parse_csv(self, content_text: str) -> List[Tuple[Optional[int], Optional[str], str]]:
        """Parses CSV rows into structured textual entries."""
        reader = csv.DictReader(io.StringIO(content_text))
        rows = []
        for i, row in enumerate(reader):
            fields = [f"{k}: {v}" for k, v in row.items() if v]
            row_text = " | ".join(fields)
            rows.append((None, f"Record {i + 1}", row_text))
        return rows

    def parse_json(self, content_text: str) -> List[Tuple[Optional[int], Optional[str], str]]:
        """Parses JSON data (array or object) into structured textual items."""
        data = json.loads(content_text)
        items = []
        if isinstance(data, list):
            for i, elem in enumerate(data):
                if isinstance(elem, dict):
                    text = " | ".join([f"{k}: {v}" for k, v in elem.items() if v])
                else:
                    text = str(elem)
                items.append((None, f"Item {i + 1}", text))
        elif isinstance(data, dict):
            for k, v in data.items():
                items.append((None, str(k), str(v)))
        else:
            items.append((None, "Content", str(data)))
        return items

    def _split_into_chunks(
        self,
        text: str,
        page_number: Optional[int] = None,
        section_heading: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Splits text into overlapping sliding window chunks."""
        chunks = []
        text = text.strip()
        if len(text) <= self.CHUNK_SIZE:
            return [{
                "page_number": page_number,
                "section_heading": section_heading,
                "content": text,
            }]

        start = 0
        while start < len(text):
            end = start + self.CHUNK_SIZE
            chunk_str = text[start:end].strip()
            if chunk_str:
                chunks.append({
                    "page_number": page_number,
                    "section_heading": section_heading,
                    "content": chunk_str,
                })
            start += (self.CHUNK_SIZE - self.CHUNK_OVERLAP)

        return chunks

    def ingest_document(
        self,
        db: Session,
        title: str,
        source_type: str,
        content_bytes_or_str: Union[bytes, str],
        filename: Optional[str] = None,
        description: Optional[str] = None,
    ) -> KnowledgeDocument:
        """Ingests, parses, chunks, and indexes a document into the knowledge base."""
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        st_clean = source_type.lower().strip()

        # Extract structured sections [(page, heading, text)]
        sections: List[Tuple[Optional[int], Optional[str], str]] = []

        if st_clean == "pdf":
            content_bytes = content_bytes_or_str if isinstance(content_bytes_or_str, bytes) else content_bytes_or_str.encode("utf-8")
            sections = self.parse_pdf(content_bytes)
        elif st_clean in ("markdown", "md", "catalogue"):
            content_str = content_bytes_or_str.decode("utf-8") if isinstance(content_bytes_or_str, bytes) else content_bytes_or_str
            sections = self.parse_markdown(content_str)
        elif st_clean == "csv":
            content_str = content_bytes_or_str.decode("utf-8") if isinstance(content_bytes_or_str, bytes) else content_bytes_or_str
            sections = self.parse_csv(content_str)
        elif st_clean == "json":
            content_str = content_bytes_or_str.decode("utf-8") if isinstance(content_bytes_or_str, bytes) else content_bytes_or_str
            sections = self.parse_json(content_str)
        else:
            # Plain text
            content_str = content_bytes_or_str.decode("utf-8") if isinstance(content_bytes_or_str, bytes) else content_bytes_or_str
            sections = [(None, "General", content_str)]

        raw_chunks = []
        for page_num, heading, sec_text in sections:
            sec_chunks = self._split_into_chunks(sec_text, page_number=page_num, section_heading=heading)
            raw_chunks.extend(sec_chunks)

        provider = self.provider

        doc = KnowledgeDocument(
            id=doc_id,
            title=title,
            source_type=st_clean,
            filename=filename,
            description=description,
            chunk_count=len(raw_chunks),
            embedding_model=provider.model_name,
            embedding_version=provider.version,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.flush()

        chunk_texts = [ch["content"] for ch in raw_chunks]
        embeddings = provider.embed_texts(chunk_texts)

        for idx, ch in enumerate(raw_chunks):
            embedding = embeddings[idx] if idx < len(embeddings) else [0.0] * provider.dimension
            chunk_obj = KnowledgeChunk(
                id=f"chk-{uuid.uuid4().hex[:12]}",
                document_id=doc_id,
                chunk_index=idx,
                page_number=ch["page_number"],
                section_heading=ch["section_heading"],
                content=ch["content"],
                vector_json=json.dumps(embedding),
                metadata_json=json.dumps({
                    "title": title,
                    "source_type": st_clean,
                    "filename": filename,
                    "embedding_model": provider.model_name,
                    "embedding_version": provider.version,
                    "embedding_dim": provider.dimension,
                }),
                created_at=datetime.now(timezone.utc),
            )
            db.add(chunk_obj)

        db.commit()
        db.refresh(doc)
        logger.info(
            "Ingested document '%s' with %d chunks (source=%s, model=%s)",
            title, len(raw_chunks), st_clean, provider.model_name
        )
        return doc

    def delete_document(self, db: Session, document_id: str) -> bool:
        """Deletes a document and all its indexed chunks."""
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
        if not doc:
            return False
        db.delete(doc)
        db.commit()
        logger.info("Deleted document '%s' from knowledge base", document_id)
        return True

    def list_documents(self, db: Session) -> List[Dict[str, Any]]:
        """Lists all indexed knowledge base documents."""
        docs = db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).all()
        return [
            {
                "id": d.id,
                "title": d.title,
                "source_type": d.source_type,
                "filename": d.filename,
                "description": d.description,
                "chunk_count": d.chunk_count,
                "embedding_model": getattr(d, "embedding_model", None),
                "embedding_version": getattr(d, "embedding_version", None),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]

    def rebuild_document_embeddings(
        self,
        db: Session,
        document_id: Optional[str] = None,
    ) -> int:
        """
        Safely re-computes embeddings for existing documents using the active provider.
        Preserves original document text, page numbers, headings, citations, and metadata.
        Returns the number of re-embedded chunks.
        """
        provider = self.provider
        query = db.query(KnowledgeDocument)
        if document_id:
            query = query.filter(KnowledgeDocument.id == document_id)
        docs = query.all()

        total_rebuilt = 0
        for doc in docs:
            chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).order_by(KnowledgeChunk.chunk_index).all()
            if not chunks:
                continue

            texts = [c.content for c in chunks]
            new_vectors = provider.embed_texts(texts)

            for idx, chunk in enumerate(chunks):
                chunk.vector_json = json.dumps(new_vectors[idx])
                meta = {}
                try:
                    meta = json.loads(chunk.metadata_json or "{}")
                except Exception:
                    pass
                meta["embedding_model"] = provider.model_name
                meta["embedding_version"] = provider.version
                meta["embedding_dim"] = provider.dimension
                chunk.metadata_json = json.dumps(meta)

            doc.embedding_model = provider.model_name
            doc.embedding_version = provider.version
            doc.updated_at = datetime.now(timezone.utc)
            total_rebuilt += len(chunks)

        db.commit()
        logger.info(
            "Rebuilt embeddings for %d documents (%d chunks) using model '%s' (v%s)",
            len(docs), total_rebuilt, provider.model_name, provider.version
        )
        return total_rebuilt

    def ensure_compatible_embeddings(self, db: Session) -> int:
        """Checks if stored chunks match active provider version and dimension. Rebuilds if mismatched."""
        provider = self.provider
        first_chunk = db.query(KnowledgeChunk).first()
        if not first_chunk or not first_chunk.vector_json:
            return 0

        vec = json.loads(first_chunk.vector_json)
        if len(vec) != provider.dimension:
            logger.warning(
                "Stored embedding dimension (%d) does not match active provider dimension (%d). Auto-rebuilding index...",
                len(vec), provider.dimension
            )
            return self.rebuild_document_embeddings(db)
        return 0

    def _expand_query_terms(self, query: str) -> Set[str]:
        """Expands query with transliterated, cross-lingual civic synonyms."""
        clean = query.lower()
        words = set(re.findall(r"[\w]+", clean))
        expanded = set(words)
        for term, synonyms in CIVIC_KEYWORD_EXPANSIONS.items():
            if term in clean:
                for syn in synonyms:
                    for w in re.findall(r"[\w]+", syn.lower()):
                        expanded.add(w)
        return expanded

    def search(
        self,
        db: Session,
        query: str,
        top_k: int = 4,
        min_score: float = 0.30,
        allow_auto_rebuild: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid vector and keyword retrieval across all stored chunks.
        Validates vector space compatibility, detects stale embeddings, and
        returns ranked evidence with source attribution and citations.
        """
        if not query or not query.strip():
            return []

        provider = self.provider
        query_vec = provider.embed_query(query)
        clean_words = [w for w in re.findall(r"[\w]+", query.lower()) if w not in COMMON_STOP_WORDS]
        salient_query_words = set(clean_words)
        expanded_query_words = set(self._expand_query_terms(query)) - COMMON_STOP_WORDS

        chunks = db.query(KnowledgeChunk, KnowledgeDocument).join(
            KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id
        ).all()

        if not chunks:
            return []

        # Vector space compatibility check
        first_chunk_vec = json.loads(chunks[0][0].vector_json or "[]")
        if len(first_chunk_vec) != provider.dimension:
            if allow_auto_rebuild:
                logger.warning(
                    "Detected incompatible vector dimension (%d != %d). Rebuilding embeddings...",
                    len(first_chunk_vec), provider.dimension
                )
                self.rebuild_document_embeddings(db)
                chunks = db.query(KnowledgeChunk, KnowledgeDocument).join(
                    KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id
                ).all()
            else:
                raise IncompatibleEmbeddingError(
                    f"Index embedding dimension ({len(first_chunk_vec)}) does not match query dimension ({provider.dimension})"
                )

        scored_results = []
        for chunk, doc in chunks:
            chunk_vec = json.loads(chunk.vector_json) if chunk.vector_json else []
            if len(chunk_vec) != len(query_vec):
                continue

            v_score = _cosine_similarity(query_vec, chunk_vec)

            # Keyword lexical overlap with expanded terminology and heading bonus
            content_lower = chunk.content.lower()
            heading_lower = (chunk.section_heading or "").lower()
            full_text = f"{heading_lower} {content_lower}"

            heading_hits = sum(1 for w in salient_query_words if w in heading_lower)
            heading_score = (heading_hits / len(salient_query_words)) if salient_query_words else 0.0

            content_hits = sum(1 for w in expanded_query_words if w in full_text)
            content_score = (content_hits / len(expanded_query_words)) if expanded_query_words else 0.0

            # Hybrid score: dense semantic similarity (70%), expanded content (20%), heading match (10%)
            hybrid_score = round((0.70 * v_score) + (0.20 * content_score) + (0.10 * heading_score), 4)

            if hybrid_score >= min_score and v_score >= 0.18:
                cite_parts = [f"Source: {doc.title}"]
                if chunk.page_number:
                    cite_parts.append(f"Page {chunk.page_number}")
                if chunk.section_heading:
                    cite_parts.append(f"Section: {chunk.section_heading}")
                citation = ", ".join(cite_parts)

                scored_results.append({
                    "chunk_id": chunk.id,
                    "document_id": doc.id,
                    "document_title": doc.title,
                    "source_type": doc.source_type,
                    "page_number": chunk.page_number,
                    "section_heading": chunk.section_heading,
                    "content": chunk.content,
                    "vector_score": round(v_score, 4),
                    "keyword_score": round(content_score, 4),
                    "score": round(hybrid_score, 4),
                    "citation": f"[{citation}]",
                })

        # Rank by score descending
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def seed_scheme_catalogue_if_empty(self, db: Session, force_reseed: bool = False) -> None:
        """Seeds statutory service catalogue entries into the knowledge base."""
        existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.source_type == "catalogue").first()
        if existing and not force_reseed:
            self.ensure_compatible_embeddings(db)
            return

        if existing and force_reseed:
            self.delete_document(db, existing.id)

        schemes = db.query(ServiceScheme).all()
        if not schemes:
            return

        catalogue_text_parts = []
        for s in schemes:
            docs = json.loads(s.commonly_required_documents or "[]")
            hindi_alias = SCHEME_HINDI_ALIASES.get(s.service_code, "")
            catalogue_text_parts.append(
                f"# {s.name} ({s.service_code})\n"
                f"Hindi Title: {hindi_alias}\n"
                f"Authority: {s.administering_body}\n"
                f"Eligibility: {s.basic_eligibility_criteria}\n"
                f"Statutory Fee: {s.statutory_fee_inr} INR\n"
                f"Official Portal: {s.official_application_url}\n"
                f"Official Source URL: {s.official_source_url}\n"
                f"Verification Status: {s.verification_status}\n"
                f"Description: {s.description_english}\n"
                f"Hindi Description: {s.description_hinglish}\n"
                f"Required Documents: {', '.join(docs)}\n"
            )

        full_catalogue = "\n\n".join(catalogue_text_parts)
        self.ingest_document(
            db=db,
            title="Timbre Statutory Welfare Schemes Catalogue",
            source_type="catalogue",
            content_bytes_or_str=full_catalogue,
            description="Verified and review-pending Indian government welfare schemes and statutory civic entitlements.",
        )


knowledge_service = KnowledgeService()
