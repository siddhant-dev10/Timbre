"""Unit and integration tests for the Knowledge Base RAG pipeline."""
import io
import pytest
from app.services.knowledge_service import knowledge_service, _compute_embedding, _cosine_similarity


def test_embedding_and_cosine_similarity():
    v1 = _compute_embedding("वोटर आईडी कार्ड पंजीकरण फॉर्म 6")
    v2 = _compute_embedding("वोटर आईडी कार्ड के लिए ऑनलाइन आवेदन")
    v3 = _compute_embedding("कल मौसम बहुत गर्म और धूप वाला रहेगा")

    sim_related = _cosine_similarity(v1, v2)
    sim_unrelated = _cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert len(v1) == knowledge_service.provider.dimension


def test_ingest_markdown_document(db):
    md_content = """# Election Guidelines
## Eligibility
Citizen must be 18 years of age or older on the qualifying date.

## Application
Submit Form 6 on the official portal voters.eci.gov.in with proof of age and residence.
"""
    doc = knowledge_service.ingest_document(
        db=db,
        title="Election Voter Guidelines",
        source_type="markdown",
        content_bytes_or_str=md_content,
        filename="election_guidelines.md",
    )

    assert doc.id.startswith("doc-")
    assert doc.chunk_count >= 2

    # Search for eligibility
    results = knowledge_service.search(db=db, query="18 years qualifying date eligibility", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert "Election Voter Guidelines" in top["citation"]
    assert "Eligibility" in top["citation"] or "Section" in top["citation"]
    assert "18 years" in top["content"]

    # Clean up
    knowledge_service.delete_document(db, doc.id)


def test_ingest_csv_and_search(db):
    csv_data = """scheme_name,benefit,portal
Kisan Credit,Low interest agricultural loan,https://kisan.gov.in
Solar Pump Subsidy,Up to 60 percent subsidy on solar pumps,https://pmkusum.gov.in
"""
    doc = knowledge_service.ingest_document(
        db=db,
        title="Agriculture Subsidies Dataset",
        source_type="csv",
        content_bytes_or_str=csv_data,
        filename="agri.csv",
    )
    assert doc.chunk_count == 2

    results = knowledge_service.search(db=db, query="solar pump subsidy kusum", top_k=1)
    assert len(results) == 1
    assert "Solar Pump" in results[0]["content"]
    assert "[Source: Agriculture Subsidies Dataset" in results[0]["citation"]

    knowledge_service.delete_document(db, doc.id)


def test_ingest_json_document(db):
    json_data = """[
      {"topic": "DigiLocker", "usage": "Store official digital certificates"},
      {"topic": "UMANG", "usage": "Single platform for all central and state civic services"}
    ]"""
    doc = knowledge_service.ingest_document(
        db=db,
        title="Digital India Portals",
        source_type="json",
        content_bytes_or_str=json_data,
        filename="digital_india.json",
    )
    assert doc.chunk_count == 2

    results = knowledge_service.search(db=db, query="DigiLocker digital certificates", top_k=1)
    assert len(results) == 1
    assert "DigiLocker" in results[0]["content"]

    knowledge_service.delete_document(db, doc.id)


def test_knowledge_api_endpoints(client, db):
    # Test upload via API
    sample_text = "राष्ट्रीय छात्रवृत्ति पोर्टल (NSP) पर विभिन्न सरकारी छात्रवृत्तियों के लिए आवेदन किया जा सकता है।"
    response = client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("nsp_info.txt", sample_text.encode("utf-8"), "text/plain")},
        data={"title": "NSP Portal Guidance", "source_type": "text"}
    )
    assert response.status_code == 200
    doc_id = response.json()["document_id"]

    # Search via API
    search_res = client.post(
        "/api/v1/knowledge/search",
        json={"query": "छात्रवृत्ति पोर्टल NSP", "top_k": 2}
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["count"] > 0
    assert "NSP" in search_data["results"][0]["content"]
    assert "NSP Portal Guidance" in search_data["results"][0]["citation"]

    # List documents
    list_res = client.get("/api/v1/knowledge/documents")
    assert list_res.status_code == 200
    docs = list_res.json()["documents"]
    assert any(d["id"] == doc_id for d in docs)

    # Delete document
    del_res = client.delete(f"/api/v1/knowledge/documents/{doc_id}")
    assert del_res.status_code == 200


def test_document_deletion_cascades_and_removes_all_chunks(db):
    """Verifies that deleting a document purges all child chunks with no orphans."""
    from app.models.knowledge import KnowledgeChunk
    doc = knowledge_service.ingest_document(
        db=db,
        title="Temporary Orphan Test Document",
        source_type="markdown",
        content_bytes_or_str="# Sec 1\nSome test data\n# Sec 2\nMore test data",
    )
    doc_id = doc.id
    chunks_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc_id).count()
    assert chunks_count > 0

    # Delete
    deleted = knowledge_service.delete_document(db, doc_id)
    assert deleted is True

    # Verify zero orphaned chunks
    remaining = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc_id).count()
    assert remaining == 0


def test_empty_query_and_low_confidence_behavior(db):
    """Verifies safe empty list return on blank query or gibberish with strict threshold."""
    assert knowledge_service.search(db, "") == []
    assert knowledge_service.search(db, "   ") == []

    # Nonsense with strict min_score
    res = knowledge_service.search(db, "xyzqwe123456789nonexistentterm", min_score=0.75)
    assert res == []

