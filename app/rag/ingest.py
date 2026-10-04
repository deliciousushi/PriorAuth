from pathlib import Path
import chromadb
import pymupdf

from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction
)
from app.config import VECTORSTORE_PATH

# CONFIG
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# EMBEDDING FUNCTION
def get_embedding_function():

    return SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

# CHUNK PAGE TEXT
def chunk_page_text(
    text: str,
    chunk_size: int = 1200
):
    """
    Split a single PDF page into smaller chunks.

    Important:
    We chunk each page independently so that
    page metadata can be preserved.
    """
    chunks = []

    for start in range(0, len(text), chunk_size):

        chunk = text[start:start + chunk_size]
        if chunk.strip():
            chunks.append(chunk)

    return chunks

# INGEST PATIENT DOCUMENTS
def ingest_patient_documents(
    patient_id: str,
    request_id: int,
    pdf_paths: list[str],
):
    """
    Index only the patient documents uploaded
    for the current prior authorization request.

    Each vector is associated with:

        patient_id
        request_id
        document
        page
        chunk_index

    This allows historical vectors to remain in Chroma
    without leaking into future requests.
    """
    client = chromadb.PersistentClient(
        path=VECTORSTORE_PATH
    )
    collection = client.get_or_create_collection(
        name="patient_records",
        embedding_function=get_embedding_function()
    )

    # Process ONLY current request documents
    for pdf_path_string in pdf_paths:

        pdf_path = Path(pdf_path_string)
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"Patient PDF not found: {pdf_path}"
            )

        document = pymupdf.open(pdf_path)

        try:
            for page_number, page in enumerate(
                document,
                start=1
            ):
                page_text = page.get_text()

                if not page_text.strip():
                    continue

                # Chunk this page
                chunks = chunk_page_text(
                    page_text
                )
                ids = []
                documents = []
                metadatas = []

                # Create vector records
                for chunk_index, chunk in enumerate(chunks):

                    chunk_id = (
                        f"req_{request_id}_"
                        f"{patient_id}_"
                        f"{pdf_path.stem}_"
                        f"p{page_number}_"
                        f"c{chunk_index}"
                    )
                    ids.append(chunk_id)
                    documents.append(chunk)
                    metadatas.append(
                        {
                            "patient_id": patient_id,

                            # Store as string consistently
                            # because Chroma metadata filtering
                            # will use this value.
                            "request_id": str(request_id),
                            "document": pdf_path.name,
                            "page": page_number,
                            "chunk_index": chunk_index,
                        }
                    )

                # Store vectors
                if documents:

                    collection.upsert(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas,
                    )
        finally:
            document.close()

    return collection