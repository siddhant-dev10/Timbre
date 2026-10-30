"""Knowledge Base & Agent Profile Management API Endpoints for Timbre."""
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.knowledge_service import knowledge_service
from app.services.profile_service import profile_service

logger = logging.getLogger("timbre.knowledge_api")

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base & Agent Profiles"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(3, ge=1, le=10)
    min_score: float = Field(0.12, ge=0.0, le=1.0)


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    source_type: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    content: str
    score: float
    citation: str


class SearchResponse(BaseModel):
    query: str
    count: int
    results: List[SearchResultItem]


class ProfileSelectionRequest(BaseModel):
    profile_id: str


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    """Lists all stored knowledge base documents and their chunk counts."""
    return {"documents": knowledge_service.list_documents(db)}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Ingests and indexes a PDF, Markdown, CSV, JSON, or Text document into the Knowledge Base.
    Generates subword embeddings and stores chunks with page and heading metadata.
    """
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or "uploaded_document"
    inferred_type = source_type
    if not inferred_type:
        ext = filename.split(".")[-1].lower() if "." in filename else "text"
        inferred_type = ext

    doc_title = title or filename.rsplit(".", 1)[0].replace("_", " ").title()

    try:
        doc = knowledge_service.ingest_document(
            db=db,
            title=doc_title,
            source_type=inferred_type,
            content_bytes_or_str=content_bytes,
            filename=filename,
            description=description,
        )
        return {
            "success": True,
            "document_id": doc.id,
            "title": doc.title,
            "source_type": doc.source_type,
            "chunk_count": doc.chunk_count,
        }
    except Exception as exc:
        logger.error("Failed to ingest document: %s", exc)
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {exc}") from exc


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Deletes a document and its chunks from the knowledge base."""
    success = knowledge_service.delete_document(db, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"success": True, "deleted_document_id": document_id}


@router.post("/search", response_model=SearchResponse)
def search_knowledge(request: SearchRequest, db: Session = Depends(get_db)):
    """Performs hybrid vector & lexical retrieval across knowledge base chunks."""
    results = knowledge_service.search(
        db=db,
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
    )
    return SearchResponse(
        query=request.query,
        count=len(results),
        results=[SearchResultItem(**r) for r in results],
    )


@router.post("/seed-catalogue")
def seed_catalogue(db: Session = Depends(get_db)):
    """Auto-indexes statutory welfare schemes from SQLite into the knowledge base."""
    knowledge_service.seed_scheme_catalogue_if_empty(db)
    return {"success": True, "message": "Statutory welfare schemes indexed into knowledge base."}


@router.get("/profiles")
def list_profiles():
    """Lists available conversational agent profiles."""
    return {
        "active_profile": profile_service.get_profile().id,
        "profiles": profile_service.list_profiles(),
    }


@router.post("/profiles/active")
def set_active_profile(request: ProfileSelectionRequest):
    """Sets the active conversational agent profile."""
    success = profile_service.set_active_profile(request.profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile ID not found.")
    return {"success": True, "active_profile": request.profile_id}
