"""
Vector search resolver for the BOSS system.

This module provides a resolver for performing vector search operations.
"""

import logging
import os
import numpy as np
from typing import Any, Dict, List, Optional, Union, Tuple, Set, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from boss.core.task_base import Task
from boss.core.task_result import TaskResult
from boss.core.task_status import TaskStatus
from boss.core.task_error import TaskError
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata

# Error type constants
INVALID_INPUT = "invalid_input"
MISSING_PARAMETER = "missing_parameter"
NOT_FOUND = "not_found"
INVALID_OPERATION = "invalid_operation"
INTERNAL_ERROR = "internal_error"
CONFIGURATION_ERROR = "configuration_error"


class VectorStoreType(str, Enum):
    """Supported vector store types."""
    IN_MEMORY = "in_memory"
    FAISS = "faiss"
    QDRANT = "qdrant"
    PINECONE = "pinecone"
    MILVUS = "milvus"
    WEAVIATE = "weaviate"
    REDIS = "redis"
    CHROMA = "chroma"


class EmbeddingModelType(str, Enum):
    """Supported embedding model types."""
    OPENAI = "openai"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    CUSTOM = "custom"


class VectorSearchResult:
    """
    Result of a vector search operation.
    
    Contains the document ID, content, metadata, and similarity score.
    """
    
    def __init__(
        self,
        doc_id: str,
        content: str,
        score: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize a vector search result.
        
        Args:
            doc_id: The document ID
            content: The document content
            score: The similarity score
            metadata: Optional metadata associated with the document
        """
        self.doc_id = doc_id
        self.content = content
        self.score = score
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the search result
        """
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata
        }


class InMemoryVectorStore:
    """
    A simple in-memory vector store implementation.
    
    Useful for testing and small datasets. For production use with larger datasets,
    use one of the specialized vector databases like FAISS, Qdrant, etc.
    """
    
    def __init__(self) -> None:
        """Initialize an empty in-memory vector store."""
        self.vectors: Dict[str, np.ndarray] = {}
        self.contents: Dict[str, str] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
    
    def add(self, doc_id: str, vector: np.ndarray, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a document to the vector store.
        
        Args:
            doc_id: The document ID
            vector: The document vector embedding
            content: The document content
            metadata: Optional metadata associated with the document
        """
        self.vectors[doc_id] = vector
        self.contents[doc_id] = content
        self.metadata[doc_id] = metadata or {}
    
    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[VectorSearchResult]:
        """
        Search for similar documents.
        
        Args:
            query_vector: The query vector embedding
            top_k: The number of results to return
            
        Returns:
            List of VectorSearchResult objects
        """
        if not self.vectors:
            return []
        
        # Calculate cosine similarity between query vector and all document vectors
        similarities = {}
        for doc_id, vector in self.vectors.items():
            similarity = self._cosine_similarity(query_vector, vector)
            similarities[doc_id] = similarity
        
        # Sort by similarity score (descending)
        sorted_results = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        
        # Limit to top_k results
        top_results = sorted_results[:top_k]
        
        # Convert to VectorSearchResult objects
        results = []
        for doc_id, score in top_results:
            content = self.contents.get(doc_id, "")
            metadata = self.metadata.get(doc_id, {})
            results.append(VectorSearchResult(doc_id, content, score, metadata))
        
        return results
    
    def delete(self, doc_id: str) -> bool:
        """
        Delete a document from the vector store.
        
        Args:
            doc_id: The document ID
            
        Returns:
            True if the document was deleted, False if it wasn't found
        """
        if doc_id in self.vectors:
            del self.vectors[doc_id]
            del self.contents[doc_id]
            del self.metadata[doc_id]
            return True
        return False
    
    def get(self, doc_id: str) -> Optional[VectorSearchResult]:
        """
        Get a document by ID.
        
        Args:
            doc_id: The document ID
            
        Returns:
            VectorSearchResult if found, None otherwise
        """
        if doc_id in self.vectors:
            return VectorSearchResult(
                doc_id=doc_id,
                content=self.contents[doc_id],
                score=1.0,  # Perfect match as it's a direct lookup
                metadata=self.metadata[doc_id]
            )
        return None
    
    def clear(self) -> None:
        """Clear all documents from the vector store."""
        self.vectors.clear()
        self.contents.clear()
        self.metadata.clear()
    
    def count(self) -> int:
        """
        Get the number of documents in the vector store.
        
        Returns:
            The number of documents
        """
        return len(self.vectors)
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity (0-1 where 1 is most similar)
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return np.dot(a, b) / (norm_a * norm_b)


class VectorSearchResolver(TaskResolver):
    """
    TaskResolver for semantic similarity search using vector embeddings.
    
    Features:
    - Document indexing and retrieval
    - Semantic similarity search
    - Multiple vector database backends
    - Multiple embedding models
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        vector_store_type: Union[VectorStoreType, str] = VectorStoreType.IN_MEMORY,
        embedding_model_type: Union[EmbeddingModelType, str] = EmbeddingModelType.OPENAI,
        embedding_model_name: Optional[str] = None,
        vector_store_config: Optional[Dict[str, Any]] = None,
        embedding_model_config: Optional[Dict[str, Any]] = None,
        custom_embedder: Optional[Callable[[str], np.ndarray]] = None
    ) -> None:
        """
        Initialize the VectorSearchResolver.
        
        Args:
            metadata: Metadata for this resolver
            vector_store_type: The type of vector store to use
            embedding_model_type: The type of embedding model to use
            embedding_model_name: Optional specific model name
            vector_store_config: Optional configuration for the vector store
            embedding_model_config: Optional configuration for the embedding model
            custom_embedder: Optional custom embedding function
        """
        super().__init__(metadata)
        self.logger = logging.getLogger(__name__)
        
        # Convert string enum values to enum instances if needed
        if isinstance(vector_store_type, str):
            vector_store_type = VectorStoreType(vector_store_type)
        if isinstance(embedding_model_type, str):
            embedding_model_type = EmbeddingModelType(embedding_model_type)
            
        self.vector_store_type = vector_store_type
        self.embedding_model_type = embedding_model_type
        self.embedding_model_name = embedding_model_name
        self.vector_store_config = vector_store_config or {}
        self.embedding_model_config = embedding_model_config or {}
        self.custom_embedder = custom_embedder
        
        # Initialize vector store and embedding model
        self.vector_store = self._initialize_vector_store()
        self.embedding_model = self._initialize_embedding_model()
    
    async def health_check(self) -> bool:
        """
        Perform a health check on this resolver.
        
        Returns:
            True if the resolver is healthy, False otherwise
        """
        # Check if vector store and embedding model are initialized
        return self.vector_store is not None and self.embedding_model is not None
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        # Check if the task specifically requests this resolver
        resolver_name = task.metadata.get("resolver", "") if task.metadata else ""
        if resolver_name == self.metadata.name or resolver_name == "":
            # Check if the task has an operation field and if it's supported
            if isinstance(task.input_data, dict):
                operation = task.input_data.get("operation", "")
                supported_ops = [
                    "index", "search", "delete", "get", "clear", "count", 
                    "batch_index", "batch_search", "batch_delete", "upsert"
                ]
                return operation in supported_ops
        
        return False
    
    async def _resolve_task(self, task: Task) -> TaskResult:
        """
        Resolve a vector search task.
        
        Args:
            task: The task to resolve
            
        Returns:
            The result of the vector search operation
        """
        # Validate task input
        if not isinstance(task.input_data, dict):
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="Input data must be a dictionary",
                    task=task,
                    error_type=INVALID_INPUT
                )
            )
        
        try:
            input_data = task.input_data
            operation = input_data.get("operation", "")
            
            # Handle different operations
            if operation == "index":
                return await self._handle_index(task)
            elif operation == "search":
                return await self._handle_search(task)
            elif operation == "delete":
                return await self._handle_delete(task)
            elif operation == "get":
                return await self._handle_get(task)
            elif operation == "clear":
                return await self._handle_clear(task)
            elif operation == "count":
                return await self._handle_count(task)
            elif operation == "batch_index":
                return await self._handle_batch_index(task)
            elif operation == "batch_search":
                return await self._handle_batch_search(task)
            elif operation == "batch_delete":
                return await self._handle_batch_delete(task)
            elif operation == "upsert":
                return await self._handle_upsert(task)
            else:
                return TaskResult(
                    task=task,
                    status=TaskStatus.ERROR,
                    error=TaskError(
                        message=f"Unknown operation: {operation}",
                        task=task,
                        error_type=INVALID_OPERATION
                    )
                )
                
        except Exception as e:
            self.logger.error(f"Error resolving task: {str(e)}")
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error resolving task: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_index(self, task: Task) -> TaskResult:
        """
        Handle an index operation to add a document to the vector store.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the result of the operation
        """
        input_data = task.input_data
        doc_id = input_data.get("doc_id")
        content = input_data.get("content")
        metadata = input_data.get("metadata")
        
        # Validate required parameters
        if not doc_id:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="doc_id is required",
                    task=task,
                    error_type=MISSING_PARAMETER
                )
            )
        
        if not content:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="content is required",
                    task=task,
                    error_type=MISSING_PARAMETER
                )
            )
        
        # Generate embedding
        try:
            vector = self._get_embedding(content)
            
            # Add to vector store
            self.vector_store.add(doc_id, vector, content, metadata)
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "doc_id": doc_id,
                    "indexed": True,
                    "vector_dimensions": len(vector)
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error indexing document: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_search(self, task: Task) -> TaskResult:
        """
        Handle a search operation to find similar documents.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the search results
        """
        input_data = task.input_data
        query = input_data.get("query")
        top_k = input_data.get("top_k", 5)
        query_vector = input_data.get("query_vector")
        filter_metadata = input_data.get("filter")
        
        # Validate required parameters
        if not query and not query_vector:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="Either query or query_vector is required",
                    task=task,
                    error_type=MISSING_PARAMETER
                )
            )
        
        try:
            # If query is provided, convert to vector
            if query and not query_vector:
                query_vector = self._get_embedding(query)
            
            # Search for similar documents
            results = self.vector_store.search(query_vector, top_k)
            
            # Apply metadata filter if provided
            if filter_metadata and results:
                filtered_results = []
                for result in results:
                    # Check if all filter conditions match
                    match = True
                    for filter_key, filter_value in filter_metadata.items():
                        if result.metadata.get(filter_key) != filter_value:
                            match = False
                            break
                    
                    if match:
                        filtered_results.append(result)
                
                results = filtered_results
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "results": [r.to_dict() for r in results],
                    "count": len(results),
                    "query": query
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error searching documents: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_delete(self, task: Task) -> TaskResult:
        """
        Handle a delete operation to remove a document from the vector store.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the result of the operation
        """
        input_data = task.input_data
        doc_id = input_data.get("doc_id")
        
        # Validate required parameters
        if not doc_id:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="doc_id is required",
                    task=task,
                    error_type=MISSING_PARAMETER
                )
            )
        
        try:
            # Delete from vector store
            deleted = self.vector_store.delete(doc_id)
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "doc_id": doc_id,
                    "deleted": deleted
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error deleting document: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_get(self, task: Task) -> TaskResult:
        """
        Handle a get operation to retrieve a document by ID.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the document if found
        """
        input_data = task.input_data
        doc_id = input_data.get("doc_id")
        
        # Validate required parameters
        if not doc_id:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="doc_id is required",
                    task=task,
                    error_type=MISSING_PARAMETER
                )
            )
        
        try:
            # Get document from vector store
            result = self.vector_store.get(doc_id)
            
            if result:
                return TaskResult(
                    task=task,
                    status=TaskStatus.COMPLETED,
                    output_data=result.to_dict()
                )
            else:
                return TaskResult(
                    task=task,
                    status=TaskStatus.ERROR,
                    error=TaskError(
                        message=f"Document not found: {doc_id}",
                        task=task,
                        error_type=NOT_FOUND
                    )
                )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error getting document: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_clear(self, task: Task) -> TaskResult:
        """
        Handle a clear operation to remove all documents from the vector store.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the result of the operation
        """
        try:
            # Get count before clearing
            count = self.vector_store.count()
            
            # Clear vector store
            self.vector_store.clear()
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "cleared": True,
                    "count": count
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error clearing vector store: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_count(self, task: Task) -> TaskResult:
        """
        Handle a count operation to get the number of documents in the vector store.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the count
        """
        try:
            # Get count
            count = self.vector_store.count()
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "count": count
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error counting documents: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_batch_index(self, task: Task) -> TaskResult:
        """
        Handle a batch index operation to add multiple documents to the vector store.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the result of the operation
        """
        input_data = task.input_data
        documents = input_data.get("documents")
        
        # Validate required parameters
        if not documents or not isinstance(documents, list):
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="documents must be a non-empty list",
                    task=task,
                    error_type=INVALID_INPUT
                )
            )
        
        try:
            results = []
            errors = []
            
            for doc in documents:
                doc_id = doc.get("doc_id")
                content = doc.get("content")
                metadata = doc.get("metadata")
                
                # Validate document
                if not doc_id or not content:
                    errors.append({
                        "doc_id": doc_id,
                        "error": "doc_id and content are required"
                    })
                    continue
                
                try:
                    # Generate embedding
                    vector = self._get_embedding(content)
                    
                    # Add to vector store
                    self.vector_store.add(doc_id, vector, content, metadata)
                    
                    results.append({
                        "doc_id": doc_id,
                        "indexed": True,
                        "vector_dimensions": len(vector)
                    })
                    
                except Exception as e:
                    errors.append({
                        "doc_id": doc_id,
                        "error": str(e)
                    })
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "results": results,
                    "errors": errors,
                    "success_count": len(results),
                    "error_count": len(errors),
                    "total": len(documents)
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error batch indexing documents: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_batch_search(self, task: Task) -> TaskResult:
        """
        Handle a batch search operation to find similar documents for multiple queries.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the search results
        """
        input_data = task.input_data
        queries = input_data.get("queries")
        top_k = input_data.get("top_k", 5)
        filter_metadata = input_data.get("filter")
        
        # Validate required parameters
        if not queries or not isinstance(queries, list):
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="queries must be a non-empty list",
                    task=task,
                    error_type=INVALID_INPUT
                )
            )
        
        try:
            batch_results = []
            errors = []
            
            for query_item in queries:
                query = query_item.get("query")
                query_id = query_item.get("query_id", f"query_{len(batch_results)}")
                query_vector = query_item.get("query_vector")
                query_top_k = query_item.get("top_k", top_k)
                
                # Validate query
                if not query and not query_vector:
                    errors.append({
                        "query_id": query_id,
                        "error": "Either query or query_vector is required"
                    })
                    continue
                
                try:
                    # If query is provided, convert to vector
                    if query and not query_vector:
                        query_vector = self._get_embedding(query)
                    
                    # Search for similar documents
                    results = self.vector_store.search(query_vector, query_top_k)
                    
                    # Apply metadata filter if provided
                    if filter_metadata and results:
                        filtered_results = []
                        for result in results:
                            # Check if all filter conditions match
                            match = True
                            for filter_key, filter_value in filter_metadata.items():
                                if result.metadata.get(filter_key) != filter_value:
                                    match = False
                                    break
                            
                            if match:
                                filtered_results.append(result)
                        
                        results = filtered_results
                    
                    batch_results.append({
                        "query_id": query_id,
                        "query": query,
                        "results": [r.to_dict() for r in results],
                        "count": len(results)
                    })
                    
                except Exception as e:
                    errors.append({
                        "query_id": query_id,
                        "error": str(e)
                    })
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "results": batch_results,
                    "errors": errors,
                    "success_count": len(batch_results),
                    "error_count": len(errors),
                    "total": len(queries)
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error batch searching documents: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_batch_delete(self, task: Task) -> TaskResult:
        """
        Handle a batch delete operation to remove multiple documents from the vector store.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the result of the operation
        """
        input_data = task.input_data
        doc_ids = input_data.get("doc_ids")
        
        # Validate required parameters
        if not doc_ids or not isinstance(doc_ids, list):
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="doc_ids must be a non-empty list",
                    task=task,
                    error_type=INVALID_INPUT
                )
            )
        
        try:
            results = []
            
            for doc_id in doc_ids:
                # Delete from vector store
                deleted = self.vector_store.delete(doc_id)
                
                results.append({
                    "doc_id": doc_id,
                    "deleted": deleted
                })
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "results": results,
                    "deleted_count": sum(1 for r in results if r["deleted"]),
                    "total": len(doc_ids)
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error batch deleting documents: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    async def _handle_upsert(self, task: Task) -> TaskResult:
        """
        Handle an upsert operation to add or update a document in the vector store.
        
        Args:
            task: The task to handle
            
        Returns:
            TaskResult with the result of the operation
        """
        input_data = task.input_data
        doc_id = input_data.get("doc_id")
        content = input_data.get("content")
        metadata = input_data.get("metadata")
        
        # Validate required parameters
        if not doc_id:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="doc_id is required",
                    task=task,
                    error_type=MISSING_PARAMETER
                )
            )
        
        if not content:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message="content is required",
                    task=task,
                    error_type=MISSING_PARAMETER
                )
            )
        
        # Delete existing document if it exists
        existing = self.vector_store.get(doc_id)
        was_update = existing is not None
        
        if was_update:
            self.vector_store.delete(doc_id)
        
        try:
            # Generate embedding
            vector = self._get_embedding(content)
            
            # Add to vector store
            self.vector_store.add(doc_id, vector, content, metadata)
            
            return TaskResult(
                task=task,
                status=TaskStatus.COMPLETED,
                output_data={
                    "doc_id": doc_id,
                    "upserted": True,
                    "was_update": was_update,
                    "vector_dimensions": len(vector)
                }
            )
            
        except Exception as e:
            return TaskResult(
                task=task,
                status=TaskStatus.ERROR,
                error=TaskError(
                    message=f"Error upserting document: {str(e)}",
                    task=task,
                    error_type=INTERNAL_ERROR
                )
            )
    
    def _initialize_vector_store(self) -> Any:
        """
        Initialize the vector store based on the configured type.
        
        Returns:
            The initialized vector store instance
        """
        if self.vector_store_type == VectorStoreType.IN_MEMORY:
            return InMemoryVectorStore()
        
        elif self.vector_store_type == VectorStoreType.FAISS:
            try:
                # Import FAISS conditionally
                import faiss
                from boss.utils.vector_stores.faiss_store import FAISSVectorStore
                
                return FAISSVectorStore(**self.vector_store_config)
            except ImportError:
                self.logger.warning("FAISS not installed, defaulting to InMemoryVectorStore")
                return InMemoryVectorStore()
                
        # Add other vector store types as needed...
        
        # Default to in-memory store
        self.logger.warning(f"Unsupported vector store type: {self.vector_store_type}, defaulting to InMemoryVectorStore")
        return InMemoryVectorStore()
    
    def _initialize_embedding_model(self) -> Any:
        """
        Initialize the embedding model based on the configured type.
        
        Returns:
            The initialized embedding model or a function that generates embeddings
        """
        if self.embedding_model_type == EmbeddingModelType.CUSTOM and self.custom_embedder:
            return self.custom_embedder
        
        elif self.embedding_model_type == EmbeddingModelType.OPENAI:
            try:
                # Import OpenAI conditionally
                from openai import OpenAI
                
                api_key = self.embedding_model_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
                model_name = self.embedding_model_name or "text-embedding-3-small"
                
                if not api_key:
                    raise ValueError("OpenAI API key not provided")
                
                client = OpenAI(api_key=api_key)
                
                def get_openai_embedding(text: str) -> np.ndarray:
                    """Generate OpenAI embedding for text."""
                    response = client.embeddings.create(
                        input=text,
                        model=model_name
                    )
                    return np.array(response.data[0].embedding)
                
                return get_openai_embedding
                
            except ImportError:
                self.logger.warning("OpenAI not installed, defaulting to random embeddings")
                return self._get_random_embedding
            except Exception as e:
                self.logger.error(f"Error initializing OpenAI embedding model: {str(e)}")
                return self._get_random_embedding
        
        elif self.embedding_model_type == EmbeddingModelType.SENTENCE_TRANSFORMERS:
            try:
                # Import sentence_transformers conditionally
                from sentence_transformers import SentenceTransformer
                
                model_name = self.embedding_model_name or "all-MiniLM-L6-v2"
                model = SentenceTransformer(model_name)
                
                def get_st_embedding(text: str) -> np.ndarray:
                    """Generate sentence_transformers embedding for text."""
                    return model.encode(text)
                
                return get_st_embedding
                
            except ImportError:
                self.logger.warning("sentence_transformers not installed, defaulting to random embeddings")
                return self._get_random_embedding
            except Exception as e:
                self.logger.error(f"Error initializing sentence_transformers model: {str(e)}")
                return self._get_random_embedding
        
        # Add other embedding model types as needed...
        
        # Default to random embeddings for demonstration
        self.logger.warning(f"Unsupported embedding model type: {self.embedding_model_type}, defaulting to random embeddings")
        return self._get_random_embedding
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Get the embedding for a text using the configured embedding model.
        
        Args:
            text: The text to embed
            
        Returns:
            The embedding vector as a numpy array
        """
        if callable(self.embedding_model):
            return self.embedding_model(text)
        return self._get_random_embedding(text)
    
    def _get_random_embedding(self, text: str) -> np.ndarray:
        """
        Generate a random embedding vector for demonstration purposes.
        
        Args:
            text: The text to embed (used only for deterministic seed)
            
        Returns:
            A random embedding vector
        """
        # Use text for deterministic seed to ensure same text gets same vector
        seed = sum(ord(c) for c in text)
        np.random.seed(seed)
        
        # Generate random embedding of dimension 384 (common dimension)
        embedding = np.random.rand(384)
        
        # Normalize to unit length
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding /= norm
            
        return embedding 