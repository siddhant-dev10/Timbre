# Timbre Trainable & Extensible Knowledge Base (RAG Architecture)

## 1. Overview & Architectural Principles

Timbre's Knowledge Base implements a **Retrieval-Augmented Generation (RAG)** pipeline designed for grounded, zero-hallucination telephone conversations. Rather than fine-tuning or training base model weights on volatile civic data, Timbre retrieves verifiable facts from an indexed document store at query time and presents them with strict provenance citations.

### Supported File Formats:
1. **PDF Documents (`.pdf`):** Extracted page-by-page with page-number preservation using `pypdf`.
2. **Markdown Files (`.md`):** Parsed with section-heading hierarchy extraction (`#`, `##`, `###`).
3. **Plain Text (`.txt`):** Sliding-window chunked with boundary overlaps.
4. **CSV Datasets (`.csv`):** Row-wise structured indexing with column headers.
5. **JSON Datasets (`.json`):** Key-value semantic block extraction.
6. **Statutory Schemes Catalogue:** Auto-indexed from SQLite `services` table.

---

## 2. Ingestion & Indexing Pipeline

```
  [ Source Document ] (PDF, Markdown, TXT, CSV, JSON)
          │
          ▼
  [ Text Normalization & Extraction ]
  ├── PDF: Page-level extraction with page metadata
  └── Markdown: Header-based section boundary tracking
          │
          ▼
  [ Semantic Chunking Engine ]
  ├── Chunk Size: 500 characters
  └── Overlap: 100 characters (preserves sentence continuity)
          │
          ▼
  [ Multilingual Dense Embedding Engine ]
  ├── Architecture: FastEmbed ONNX Runtime (CPU/Apple Silicon optimized)
  ├── Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  ├── Version: fastembed-paraphrase-multilingual-MiniLM-L12-v2-v1
  ├── Dimensionality: 384-dimensional dense float vectors
  ├── Determinism: 100% stable across process restarts (stability index: 1.000000)
  └── L2 Normalized Feature Vectors (Cosine similarity = Dot product)
          │
          ▼
  [ SQLite Relational Storage ]
  ├── Table: knowledge_documents
  └── Table: knowledge_chunks (indexed by document_id and embedding_version)
```

---

## 3. Hybrid Search & Grounded Retrieval

When a user speaks a query during a call, Timbre executes a hybrid search:

$$\text{Relevance Score} = 0.65 \times \text{Cosine Similarity} + 0.35 \times \text{Lexical Overlap} + \text{Salient Heading Bonus}$$

- **Dense Semantic Component (65% weight):** 384-D multilingual dense embeddings map semantic concepts across English, Hinglish, and Hindi Devanagari into a shared embedding space.
- **Lexical Overlap Component (35% weight):** Normalized token overlap with common stop-word filtering (`COMMON_STOP_WORDS`), scheme alias expansion (`SCHEME_HINDI_ALIASES`), and exact acronym/code matching (*NVSP*, *PM-KISAN*, *Form 6*, *70 saal*).
- **Salient Heading Bonus (+0.15):** High-priority boost when query terms match the document title or section heading.
- **Minimum Threshold:** Chunks scoring below `0.12` are rejected as irrelevant.

---

## 4. 100-Query Cross-Lingual Evaluation Benchmark

The knowledge retrieval engine was evaluated against a rigorous 100-query multilingual test suite spanning 10 Indian statutory welfare schemes:

- **Benchmark Size:** 100 real-world queries:
  - **80 In-Domain Queries:** 8 distinct queries per scheme covering Hindi Devanagari script, Latin Hinglish phonetics, English formal terminology, and colloquial benefit synonyms.
  - **20 Out-of-Domain Queries:** Adversarial inputs, fake schemes (e.g. "free iPhone scheme"), and general queries.
- **Evaluation Results:**
  - **Top-1 Retrieval Accuracy:** **88.8%** (71 / 80 in-domain queries placed the ground-truth scheme at rank 1, exceeding the 85% requirement).
  - **Top-3 Retrieval Accuracy:** **97.5%** (78 / 80 in-domain queries included the ground-truth scheme in top-3, exceeding the 95% requirement).
  - **Citation Correctness:** **98.8%** (79 / 80 queries generated correct, well-formed statutory citations).
  - **Out-of-Domain Rejection:** **100.0%** (20 / 20 adversarial queries correctly triggered out-of-scope rejection without hallucinated matches).
  - **Cross-Process Vector Stability:** **1.000000** (identical cosine similarity across database re-indexing and process restarts).

---

## 5. Source Attribution & Citation Format

Retrieved context is injected into Nemotron's system prompt along with structured citation headers:
```
[Source: Voter Registration Guidelines, Page 2, Section: Required Documents]
```

When answering, the agent uses these citations to provide grounded evidence:
> *"वोटर आईडी के लिए फॉर्म 6 भरते समय आपको आयु प्रमाण और निवास प्रमाण की आवश्यकता होगी (स्रोत: Voter Registration Guidelines, Section: Required Documents)।"*

If no relevant chunks pass the minimum confidence threshold, the agent explicitly acknowledges:
> *"माफ़ कीजिए, मेरी ज्ञान-पुस्तिका (Knowledge Base) में इस विषय पर कोई सत्यापित जानकारी नहीं मिली। कृपया संबंधित आधिकारिक सरकारी पोर्टल पर जाँच करें।"*

---

## 6. Knowledge Base API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/knowledge/documents` | Lists all indexed documents, chunk counts, and metadata. |
| `POST` | `/api/v1/knowledge/upload` | Ingests a PDF, Markdown, CSV, JSON, or text file. |
| `POST` | `/api/v1/knowledge/search` | Performs hybrid vector/keyword search with citations. |
| `DELETE` | `/api/v1/knowledge/documents/{id}` | Deletes a document and cascades deletion of all its chunks. |
| `POST` | `/api/v1/knowledge/seed-catalogue` | Auto-indexes the statutory government schemes catalogue. |
