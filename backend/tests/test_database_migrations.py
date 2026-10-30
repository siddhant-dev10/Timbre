"""Regression and QA Tests for Repeatable Database Migrations.

Verifies that:
1. An older SQLite schema lacking additive columns (citizens.record_source, citizens.archived_at,
   knowledge_documents.embedding_model, knowledge_documents.embedding_version) is migrated cleanly.
2. All existing citizen, service, knowledge document, and chunk records are preserved intact.
3. Existing rows receive safe defaults or nullable values (no invented embeddings).
4. Running migrations repeatedly is idempotent and error-free.
5. SQLAlchemy models and queries (including knowledge_service.list_documents) operate seamlessly
   post-migration without 'no such column' errors.
"""
import os
import tempfile
import sqlite3
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database.migrations import run_migrations, ADDITIVE_COLUMNS
from app.models.citizen import Citizen
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.services.knowledge_service import knowledge_service


@pytest.fixture
def older_schema_db():
    """Sets up a temporary SQLite database using the older Timbre schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Populate with legacy SQLite tables lacking newer columns
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    # Legacy citizens table without record_source and archived_at
    cur.execute("""
    CREATE TABLE citizens (
        id VARCHAR(32) NOT NULL PRIMARY KEY,
        first_name VARCHAR(64) NOT NULL,
        last_name VARCHAR(64) NOT NULL,
        name VARCHAR(128) NOT NULL,
        date_of_birth DATE NOT NULL,
        age INTEGER NOT NULL,
        gender VARCHAR(16) NOT NULL,
        state VARCHAR(64) NOT NULL,
        district VARCHAR(64) NOT NULL,
        city_or_village VARCHAR(64) NOT NULL,
        rural_or_urban VARCHAR(16) NOT NULL,
        preferred_language VARCHAR(32) NOT NULL,
        education VARCHAR(64) NOT NULL,
        occupation VARCHAR(64) NOT NULL,
        employment_status VARCHAR(32) NOT NULL,
        synthetic_family_income INTEGER NOT NULL,
        simulated_income_bracket VARCHAR(32) NOT NULL,
        family_size INTEGER NOT NULL,
        marital_status VARCHAR(32) NOT NULL,
        children INTEGER NOT NULL,
        is_student BOOLEAN NOT NULL,
        is_farmer BOOLEAN NOT NULL,
        is_senior_citizen BOOLEAN NOT NULL,
        simulated_life_event VARCHAR(128) NOT NULL,
        potentially_relevant_services TEXT NOT NULL,
        eligibility_notes TEXT NOT NULL,
        required_documents TEXT NOT NULL,
        demo_only BOOLEAN NOT NULL,
        phone_number VARCHAR(32) NOT NULL,
        email VARCHAR(64) NOT NULL,
        pincode VARCHAR(16) NOT NULL,
        created_at DATETIME,
        updated_at DATETIME
    );
    """)

    # Legacy knowledge_documents table without embedding_model and embedding_version
    cur.execute("""
    CREATE TABLE knowledge_documents (
        id VARCHAR(64) NOT NULL PRIMARY KEY,
        title VARCHAR(256) NOT NULL,
        source_type VARCHAR(32) NOT NULL,
        filename VARCHAR(256),
        description TEXT,
        chunk_count INTEGER,
        created_at DATETIME,
        updated_at DATETIME
    );
    """)

    # Legacy knowledge_chunks table
    cur.execute("""
    CREATE TABLE knowledge_chunks (
        id VARCHAR(64) NOT NULL PRIMARY KEY,
        document_id VARCHAR(64) NOT NULL,
        chunk_index INTEGER NOT NULL,
        page_number INTEGER,
        section_heading VARCHAR(256),
        content TEXT NOT NULL,
        vector_json TEXT,
        metadata_json TEXT,
        created_at DATETIME,
        FOREIGN KEY(document_id) REFERENCES knowledge_documents (id) ON DELETE CASCADE
    );
    """)

    # Insert legacy records
    cur.execute("""
    INSERT INTO citizens (
        id, first_name, last_name, name, date_of_birth, age, gender,
        state, district, city_or_village, rural_or_urban, preferred_language,
        education, occupation, employment_status, synthetic_family_income,
        simulated_income_bracket, family_size, marital_status, children,
        is_student, is_farmer, is_senior_citizen, simulated_life_event,
        potentially_relevant_services, eligibility_notes, required_documents,
        demo_only, phone_number, email, pincode
    ) VALUES (
        'CIT-LEGACY-01', 'Ramesh', 'Kumar', 'Ramesh Kumar', '1985-06-15', 41, 'Male',
        'Rajasthan', 'Jaipur', 'Chomu', 'RURAL', 'Hindi',
        '10th Pass', 'Farmer', 'Self-Employed', 95000,
        'LOW', 4, 'Married', 2,
        0, 1, 0, 'Approaching 42',
        '[]', 'Eligible for KCC', '[]',
        1, '+919876543210', 'ramesh@example.com', '303702'
    );
    """)

    cur.execute("""
    INSERT INTO knowledge_documents (
        id, title, source_type, filename, description, chunk_count
    ) VALUES (
        'doc-legacy-001', 'Legacy Scheme Manual', 'pdf', 'manual.pdf', 'Historic documentation', 1
    );
    """)

    cur.execute("""
    INSERT INTO knowledge_chunks (
        id, document_id, chunk_index, page_number, section_heading, content, vector_json
    ) VALUES (
        'chk-legacy-001', 'doc-legacy-001', 0, 1, 'Introduction', 'Legacy scheme details for farmers.', '[0.1, 0.2, 0.3]'
    );
    """)

    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{path}")
    yield engine, path

    engine.dispose()
    if os.path.exists(path):
        os.remove(path)


def test_migration_adds_missing_columns_and_preserves_records(older_schema_db):
    engine, _ = older_schema_db
    inspector = inspect(engine)

    # Verify initial missing state in older schema
    doc_cols_before = {c["name"] for c in inspector.get_columns("knowledge_documents")}
    citizen_cols_before = {c["name"] for c in inspector.get_columns("citizens")}
    assert "embedding_model" not in doc_cols_before
    assert "embedding_version" not in doc_cols_before
    assert "record_source" not in citizen_cols_before
    assert "archived_at" not in citizen_cols_before

    # Verify that attempting to query KnowledgeDocument before migration fails
    Session = sessionmaker(bind=engine)
    session = Session()
    with pytest.raises(Exception) as exc_info:
        session.query(KnowledgeDocument).all()
    assert "no such column" in str(exc_info.value).lower()
    session.close()

    # Execute migration
    applied = run_migrations(engine)
    assert applied >= 4

    # Re-inspect schema
    inspector = inspect(engine)
    doc_cols_after = {c["name"] for c in inspector.get_columns("knowledge_documents")}
    citizen_cols_after = {c["name"] for c in inspector.get_columns("citizens")}

    assert "embedding_model" in doc_cols_after
    assert "embedding_version" in doc_cols_after
    assert "record_source" in citizen_cols_after
    assert "archived_at" in citizen_cols_after

    # Verify existing records are preserved with safe defaults/nulls
    session = Session()
    try:
        # Check citizen record
        citizen = session.query(Citizen).filter(Citizen.id == "CIT-LEGACY-01").first()
        assert citizen is not None
        assert citizen.name == "Ramesh Kumar"
        assert citizen.record_source == "synthetic"
        assert citizen.archived_at is None

        # Check knowledge document record
        doc = session.query(KnowledgeDocument).filter(KnowledgeDocument.id == "doc-legacy-001").first()
        assert doc is not None
        assert doc.title == "Legacy Scheme Manual"
        assert doc.chunk_count == 1
        assert doc.embedding_model is None
        assert doc.embedding_version is None

        # Check knowledge chunk record
        chunk = session.query(KnowledgeChunk).filter(KnowledgeChunk.id == "chk-legacy-001").first()
        assert chunk is not None
        assert chunk.content == "Legacy scheme details for farmers."
        assert chunk.vector_json == "[0.1, 0.2, 0.3]"

        # Verify service methods like list_documents work without error
        docs = knowledge_service.list_documents(session)
        assert len(docs) == 1
        assert docs[0]["id"] == "doc-legacy-001"
        assert docs[0]["embedding_model"] is None
        assert docs[0]["embedding_version"] is None
    finally:
        session.close()


def test_migration_is_idempotent(older_schema_db):
    engine, _ = older_schema_db

    # Run migration first time
    applied_first = run_migrations(engine)
    assert applied_first >= 4

    # Run migration second time
    applied_second = run_migrations(engine)
    assert applied_second == 0

    # Run migration third time
    applied_third = run_migrations(engine)
    assert applied_third == 0
