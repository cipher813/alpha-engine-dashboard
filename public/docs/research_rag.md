## Research — RAG & Vector DB

This deep dive covers how the Research module uses Retrieval-Augmented Generation
(RAG) to give LLM agents access to SEC filings and historical investment theses
through semantic search.

---

### What Is RAG?

Retrieval-Augmented Generation is a pattern where an LLM's response is grounded
in retrieved documents rather than relying solely on its training data. Instead
of asking the model to recall facts about a company, the system:

1. **Embeds** a query into a vector representation
2. **Searches** a vector database for semantically similar documents
3. **Injects** the retrieved documents into the LLM's context
4. **Generates** a response grounded in real source material

This is particularly valuable for financial analysis where the LLM needs to
reason over specific company filings and earnings transcripts — primary source
documents that aren't part of the model's general knowledge.

---

### Architecture

```
Ingestion Pipeline              Vector Database              Agent Tool
┌─────────────────┐         ┌──────────────────┐        ┌──────────────┐
│ SEC EDGAR API   │         │ Neon PostgreSQL   │        │ query_filings│
│ 10-K, 10-Q     │──chunk──│ + pgvector        │──search─│ @tool        │
│ filings         │  embed  │ (HNSW index)      │        │              │
├─────────────────┤         │                   │        │ Returns:     │
│ Thesis History  │──chunk──│ rag.documents     │        │ - content    │
│ (investment     │  embed  │ rag.chunks        │        │ - filed_date │
│  theses)        │         │ 512d vectors      │        │ - section    │
└─────────────────┘         └──────────────────┘        │ - similarity │
                                                         └──────────────┘
```

---

### Components

#### Embeddings

The system uses **Voyage voyage-3-lite** (512 dimensions) for embedding both
documents and queries. Voyage is a specialized embedding model optimized for
retrieval tasks, with separate input types for documents and queries:

- **Documents:** Embedded with `input_type='document'` during ingestion
- **Queries:** Embedded with `input_type='query'` during retrieval
- **Batch support:** Multiple texts embedded in a single API call for efficiency

#### Vector Database

**Neon PostgreSQL with pgvector** provides the vector storage and similarity
search:

- **`rag.documents`** — Document metadata (ticker, doc_type, filed_date, source)
- **`rag.chunks`** — Text chunks with 512-dimensional embedding vectors
- **HNSW index** — Hierarchical Navigable Small World index for fast approximate
  nearest-neighbor search

Neon was chosen over alternatives (Pinecone, ChromaDB, FAISS) for its managed
PostgreSQL compatibility and pgvector's mature indexing.

#### Ingestion Pipelines

Three pipelines populate the vector database:

| Pipeline | Source | Sections Extracted |
|----------|--------|--------------------|
| SEC filings | EDGAR API | Risk Factors, MD&A, Business Overview, Market Risk |
| Thesis history | Internal | Bull case, bear case, catalysts, risks, conviction |
| Earnings transcripts | (planned) | Management commentary, Q&A highlights |

**Chunking strategy:** Documents are split at ~400 tokens with 50-token overlap
to preserve context across chunk boundaries. Section labels are preserved as
metadata for filtering.

---

### Retrieval Flow

When a qualitative analyst agent needs to research a company's SEC filings:

```
1. Agent calls: query_filings("AAPL", "what are the key risk factors?", "10-K")

2. Voyage embeds the query (input_type='query')

3. SQL query with metadata pre-filtering:
   - WHERE ticker = 'AAPL'
   - AND doc_type IN ('10-K')
   - AND filed_date >= min_date
   - ORDER BY embedding <=> query_vector  (cosine distance)
   - LIMIT top_k

4. Returns top-k results:
   [
     {"content": "...", "filed_date": "2025-11-01", "section": "Risk Factors", "similarity": 0.87},
     {"content": "...", "filed_date": "2025-11-01", "section": "MD&A", "similarity": 0.82},
     ...
   ]

5. Agent incorporates findings into its analysis
```

**Metadata pre-filtering** is critical for performance — it narrows the search
space before the vector similarity computation, and ensures results are relevant
to the specific company and document type.

---

### Why Not a Pure Vector Store?

The system also maintains a traditional **S3-based thesis archive** alongside
the vector database. This dual approach exists because:

- **S3 archive:** Complete, structured thesis records (JSON) for deterministic
  access. When the system needs "the most recent thesis for AAPL," it reads
  a specific S3 path. No embedding or similarity search needed.
- **Vector DB:** Semantic search across unstructured text. When the system needs
  "what did recent filings say about supply chain risks," it searches by meaning
  rather than exact keywords.

The two systems serve complementary needs: structured retrieval (S3) for known
queries and semantic retrieval (pgvector) for exploratory analysis.

---

### Design Decisions

**Embedding model choice:** Voyage voyage-3-lite was selected over OpenAI
ada-002 and Cohere embed-v3 based on retrieval benchmarks for financial text.
The 512-dimension model balances retrieval quality with storage and compute efficiency.

**pgvector over dedicated vector DBs:** Pinecone and Weaviate offer more
features (hybrid search, auto-scaling), but pgvector on Neon provides:
- Standard SQL for metadata filtering (no proprietary query language)
- Managed PostgreSQL with automatic backups
- HNSW indexing for sub-millisecond search

**Chunk size (400 tokens):** Balances specificity (smaller chunks = more precise
retrieval) with context (larger chunks = more coherent text). The 50-token
overlap ensures that key sentences split across chunk boundaries are captured
in at least one chunk.

---

### Future Directions

- **Earnings transcripts:** Pipeline is built but awaiting a reliable data source
  (the original provider deprecated their endpoint)
- **Cross-ticker retrieval:** Currently filtered to single ticker; expanding to
  sector-level queries (e.g., "semiconductor supply chain risks across all tech
  holdings") would enable richer comparative analysis
- **Hybrid search:** Combining vector similarity with keyword (BM25) matching for
  queries where specific terms matter (e.g., "Section 404 compliance")
