"""
Vector Store Module
Handles document embeddings and similarity search using ChromaDB
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .document_processor import DocumentChunk, ProcessedDocument
from .config import settings


@dataclass
class SearchResult:
    """Represents a search result from the vector store"""
    content: str
    source_file: str
    document_type: str
    similarity_score: float
    metadata: Dict
    answer_content: Optional[str] = None


class VectorStore:
    """Manages document embeddings and similarity search"""

    def __init__(self):
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
        self._initialized = False

    def _initialize(self):
        """Lazy initialization of embedding model and vector store"""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            # Initialize embedding model
            print(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)

            # Initialize ChromaDB
            chroma_settings = ChromaSettings(
                persist_directory=settings.CHROMA_PERSIST_DIR,
                anonymized_telemetry=False
            )

            self.chroma_client = chromadb.Client(chroma_settings)

            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name=settings.COLLECTION_NAME,
                metadata={"description": "RFP documents and answers"}
            )

            self._initialized = True
            print(f"Vector store initialized. Collection has {self.collection.count()} documents.")

        except ImportError as e:
            raise ImportError(
                f"Required packages not installed: {e}. "
                "Install with: pip install sentence-transformers chromadb"
            )

    def _generate_id(self, content: str, source: str) -> str:
        """Generate a unique ID for a document chunk"""
        combined = f"{source}:{content[:100]}"
        return hashlib.md5(combined.encode()).hexdigest()

    def add_document_pair(
        self,
        rfp_doc: ProcessedDocument,
        answer_doc: ProcessedDocument,
        pair_id: Optional[str] = None
    ) -> Dict:
        """Add an RFP and its corresponding answer as a linked pair"""
        self._initialize()

        if pair_id is None:
            pair_id = hashlib.md5(
                f"{rfp_doc.filename}:{answer_doc.filename}".encode()
            ).hexdigest()[:12]

        ids = []
        documents = []
        metadatas = []
        embeddings = []

        # Process RFP chunks
        for chunk in rfp_doc.chunks:
            chunk_id = self._generate_id(chunk.content, chunk.source_file)
            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append({
                "source_file": chunk.source_file,
                "document_type": "rfp",
                "chunk_index": chunk.chunk_index,
                "pair_id": pair_id,
                "answer_file": answer_doc.filename,
                **chunk.metadata
            })

        # Process answer chunks
        for chunk in answer_doc.chunks:
            chunk_id = self._generate_id(chunk.content, chunk.source_file)
            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append({
                "source_file": chunk.source_file,
                "document_type": "answer",
                "chunk_index": chunk.chunk_index,
                "pair_id": pair_id,
                "rfp_file": rfp_doc.filename,
                **chunk.metadata
            })

        # Generate embeddings
        print(f"Generating embeddings for {len(documents)} chunks...")
        embeddings = self.embedding_model.encode(documents).tolist()

        # Add to collection
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )

        return {
            "pair_id": pair_id,
            "rfp_chunks": len(rfp_doc.chunks),
            "answer_chunks": len(answer_doc.chunks),
            "total_chunks": len(ids)
        }

    def add_single_document(self, doc: ProcessedDocument) -> Dict:
        """Add a single document (either RFP or answer)"""
        self._initialize()

        ids = []
        documents = []
        metadatas = []

        for chunk in doc.chunks:
            chunk_id = self._generate_id(chunk.content, chunk.source_file)
            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append({
                "source_file": chunk.source_file,
                "document_type": doc.document_type,
                "chunk_index": chunk.chunk_index,
                **chunk.metadata
            })

        # Generate embeddings
        embeddings = self.embedding_model.encode(documents).tolist()

        # Add to collection
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )

        return {
            "filename": doc.filename,
            "chunks_added": len(ids)
        }

    def search_similar(
        self,
        query: str,
        top_k: int = None,
        document_type: Optional[str] = None,
        include_answers: bool = True
    ) -> List[SearchResult]:
        """Search for similar documents/chunks"""
        self._initialize()

        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        # Generate query embedding
        query_embedding = self.embedding_model.encode([query])[0].tolist()

        # Build where clause for filtering
        where_clause = None
        if document_type:
            where_clause = {"document_type": document_type}

        # Query the collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2 if include_answers else top_k,  # Get more results to find pairs
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )

        search_results = []
        seen_pairs = set()

        if results and results['ids'] and len(results['ids']) > 0:
            for i, (doc_id, document, metadata, distance) in enumerate(zip(
                results['ids'][0],
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                # Convert distance to similarity score (ChromaDB uses L2 distance)
                similarity = 1 / (1 + distance)

                if similarity < settings.SIMILARITY_THRESHOLD:
                    continue

                # Try to find corresponding answer if this is an RFP chunk
                answer_content = None
                if include_answers and metadata.get('document_type') == 'rfp':
                    pair_id = metadata.get('pair_id')
                    if pair_id and pair_id not in seen_pairs:
                        seen_pairs.add(pair_id)
                        # Find corresponding answer chunks
                        answer_results = self.collection.query(
                            query_embeddings=[query_embedding],
                            n_results=3,
                            where={
                                "$and": [
                                    {"pair_id": pair_id},
                                    {"document_type": "answer"}
                                ]
                            },
                            include=["documents"]
                        )
                        if answer_results['documents'] and answer_results['documents'][0]:
                            answer_content = "\n\n".join(answer_results['documents'][0])

                search_results.append(SearchResult(
                    content=document,
                    source_file=metadata.get('source_file', 'unknown'),
                    document_type=metadata.get('document_type', 'unknown'),
                    similarity_score=similarity,
                    metadata=metadata,
                    answer_content=answer_content
                ))

        # Sort by similarity and limit
        search_results.sort(key=lambda x: x.similarity_score, reverse=True)
        return search_results[:top_k]

    def get_all_pairs(self) -> List[Dict]:
        """Get all RFP-Answer pairs in the store"""
        self._initialize()

        # Get all documents
        all_docs = self.collection.get(include=["metadatas"])

        pairs = {}
        for metadata in all_docs['metadatas']:
            pair_id = metadata.get('pair_id')
            if pair_id:
                if pair_id not in pairs:
                    pairs[pair_id] = {
                        'pair_id': pair_id,
                        'rfp_file': None,
                        'answer_file': None,
                        'rfp_chunks': 0,
                        'answer_chunks': 0
                    }

                if metadata.get('document_type') == 'rfp':
                    pairs[pair_id]['rfp_file'] = metadata.get('source_file')
                    pairs[pair_id]['rfp_chunks'] += 1
                elif metadata.get('document_type') == 'answer':
                    pairs[pair_id]['answer_file'] = metadata.get('source_file')
                    pairs[pair_id]['answer_chunks'] += 1

        return list(pairs.values())

    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        self._initialize()

        total_count = self.collection.count()

        # Get document type breakdown
        all_docs = self.collection.get(include=["metadatas"])

        rfp_count = 0
        answer_count = 0
        unique_files = set()

        for metadata in all_docs['metadatas']:
            doc_type = metadata.get('document_type')
            if doc_type == 'rfp':
                rfp_count += 1
            elif doc_type == 'answer':
                answer_count += 1
            unique_files.add(metadata.get('source_file'))

        return {
            "total_chunks": total_count,
            "rfp_chunks": rfp_count,
            "answer_chunks": answer_count,
            "unique_files": len(unique_files),
            "pairs": len(self.get_all_pairs())
        }

    def delete_by_source(self, source_file: str) -> int:
        """Delete all chunks from a specific source file"""
        self._initialize()

        # Get IDs of documents to delete
        results = self.collection.get(
            where={"source_file": source_file},
            include=["metadatas"]
        )

        if results['ids']:
            self.collection.delete(ids=results['ids'])
            return len(results['ids'])

        return 0

    def clear_all(self):
        """Clear all documents from the store"""
        self._initialize()

        # Delete and recreate collection
        self.chroma_client.delete_collection(settings.COLLECTION_NAME)
        self.collection = self.chroma_client.create_collection(
            name=settings.COLLECTION_NAME,
            metadata={"description": "RFP documents and answers"}
        )
