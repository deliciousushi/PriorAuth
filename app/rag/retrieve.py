import chromadb
from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction
)
from app.config import VECTORSTORE_PATH

# CONFIG
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# PATIENT RETRIEVER
class PatientRetriever:

    def __init__(
        self,
        request_id: int,
    ):
        self.request_id = request_id
        self.client = chromadb.PersistentClient(
            path=VECTORSTORE_PATH
        )
        self.collection = self.client.get_or_create_collection(
            name="patient_records",
            embedding_function=SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
        )

    # SEARCH
    def search(
        self,
        patient_id: str,
        query: str,
        top_k: int = 5,
    ):
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,

            # CRITICAL SECURITY / ISOLATION FILTER
            where={
                "$and": [
                    {
                        "patient_id": {
                            "$eq": patient_id
                        }
                    },
                    {
                        "request_id": {
                            "$eq": str(self.request_id)
                        }
                    },
                ]
            }
        )
        documents = results.get(
            "documents",
            [[]]
        )[0]

        metadatas = results.get(
            "metadatas",
            [[]]
        )[0]

        output = []

        for document, metadata in zip(
            documents,
            metadatas
        ):
            output.append(
                {
                    "document": metadata.get(
                        "document"
                    ),

                    "page": metadata.get(
                        "page"
                    ),

                    "reference": (
                        f"Page {metadata.get('page')}"
                        if metadata.get("page")
                        else None
                    ),

                    "text": document,
                }
            )
        return output