"""
Tests for the VectorSearchResolver component.

This module contains unit tests for the vector search capabilities,
including document indexing, retrieval, and semantic similarity search.
"""

import unittest
import asyncio
import numpy as np
from unittest.mock import MagicMock, patch

from boss.core.task_models import Task, TaskStatus
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.vector_search_resolver import (
    VectorSearchResolver,
    VectorStoreType,
    EmbeddingModelType,
    VectorSearchResult,
    InMemoryVectorStore
)


class TestInMemoryVectorStore(unittest.TestCase):
    """Tests for the InMemoryVectorStore class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.store = InMemoryVectorStore()
        
        # Add some test documents
        self.doc1_id = "doc1"
        self.doc1_content = "This is a document about artificial intelligence."
        self.doc1_vector = np.array([0.1, 0.2, 0.3])
        self.doc1_metadata = {"category": "AI", "author": "Smith"}
        
        self.doc2_id = "doc2"
        self.doc2_content = "Machine learning is a subset of artificial intelligence."
        self.doc2_vector = np.array([0.2, 0.3, 0.4])
        self.doc2_metadata = {"category": "AI", "author": "Jones"}
        
        self.doc3_id = "doc3"
        self.doc3_content = "Data science involves statistics and programming."
        self.doc3_vector = np.array([0.3, 0.4, 0.5])
        self.doc3_metadata = {"category": "Data Science", "author": "Johnson"}
        
        # Add documents to store
        self.store.add(self.doc1_id, self.doc1_vector, self.doc1_content, self.doc1_metadata)
        self.store.add(self.doc2_id, self.doc2_vector, self.doc2_content, self.doc2_metadata)
        self.store.add(self.doc3_id, self.doc3_vector, self.doc3_content, self.doc3_metadata)
    
    def test_add_document(self):
        """Test adding a document to the store."""
        # Add a new document
        new_doc_id = "doc4"
        new_doc_content = "Natural language processing is used in chatbots."
        new_doc_vector = np.array([0.4, 0.5, 0.6])
        new_doc_metadata = {"category": "NLP", "author": "Brown"}
        
        self.store.add(new_doc_id, new_doc_vector, new_doc_content, new_doc_metadata)
        
        # Verify document was added
        self.assertEqual(self.store.count(), 4)
        self.assertIn(new_doc_id, self.store.contents)
        self.assertEqual(self.store.contents[new_doc_id], new_doc_content)
        self.assertEqual(self.store.metadata[new_doc_id], new_doc_metadata)
        np.testing.assert_array_equal(self.store.vectors[new_doc_id], new_doc_vector)
    
    def test_search(self):
        """Test searching for similar documents."""
        query_vector = np.array([0.15, 0.25, 0.35])
        results = self.store.search(query_vector, top_k=2)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], VectorSearchResult)
        
        # The closest document should be doc1 or doc2 based on cosine similarity
        self.assertIn(results[0].doc_id, [self.doc1_id, self.doc2_id])
    
    def test_search_empty_store(self):
        """Test searching an empty store."""
        empty_store = InMemoryVectorStore()
        query_vector = np.array([0.1, 0.2, 0.3])
        results = empty_store.search(query_vector)
        
        # Verify results
        self.assertEqual(len(results), 0)
    
    def test_delete(self):
        """Test deleting a document."""
        # Delete document
        result = self.store.delete(self.doc1_id)
        
        # Verify document was deleted
        self.assertTrue(result)
        self.assertEqual(self.store.count(), 2)
        self.assertNotIn(self.doc1_id, self.store.contents)
        
        # Try to delete non-existent document
        result = self.store.delete("non_existent_doc")
        self.assertFalse(result)
    
    def test_get(self):
        """Test getting a document by ID."""
        # Get existing document
        result = self.store.get(self.doc1_id)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.doc_id, self.doc1_id)
        self.assertEqual(result.content, self.doc1_content)
        self.assertEqual(result.metadata, self.doc1_metadata)
        self.assertEqual(result.score, 1.0)  # Perfect match
        
        # Try to get non-existent document
        result = self.store.get("non_existent_doc")
        self.assertIsNone(result)
    
    def test_clear(self):
        """Test clearing the store."""
        self.store.clear()
        
        # Verify store is empty
        self.assertEqual(self.store.count(), 0)
        self.assertEqual(len(self.store.vectors), 0)
        self.assertEqual(len(self.store.contents), 0)
        self.assertEqual(len(self.store.metadata), 0)
    
    def test_count(self):
        """Test counting documents."""
        # Verify initial count
        self.assertEqual(self.store.count(), 3)
        
        # Add a document
        self.store.add("doc4", np.array([0.4, 0.5, 0.6]), "New document", {})
        self.assertEqual(self.store.count(), 4)
        
        # Delete a document
        self.store.delete(self.doc1_id)
        self.assertEqual(self.store.count(), 3)
        
        # Clear store
        self.store.clear()
        self.assertEqual(self.store.count(), 0)
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        a = np.array([1, 0, 0])
        b = np.array([0, 1, 0])
        c = np.array([1, 1, 0])
        
        # Orthogonal vectors should have 0 similarity
        self.assertEqual(self.store._cosine_similarity(a, b), 0.0)
        
        # Same vector should have 1.0 similarity
        self.assertEqual(self.store._cosine_similarity(a, a), 1.0)
        
        # Vectors at 45 degrees should have 0.7071 similarity (approximately)
        self.assertAlmostEqual(self.store._cosine_similarity(a, c), 0.7071, places=4)
        
        # Zero vector handling
        zero_vector = np.array([0, 0, 0])
        self.assertEqual(self.store._cosine_similarity(a, zero_vector), 0.0)
        self.assertEqual(self.store._cosine_similarity(zero_vector, a), 0.0)


class TestVectorSearchResolver(unittest.TestCase):
    """Tests for the VectorSearchResolver class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        metadata = TaskResolverMetadata(
            name="vector_search",
            version="1.0.0",
            description="Vector search resolver for testing"
        )
        
        # Create resolver with in-memory store and custom embedder
        def test_embedder(text):
            """Simple deterministic embedder for testing."""
            # Hash the text to create a deterministic seed
            seed = sum(ord(c) for c in text)
            np.random.seed(seed)
            embedding = np.random.rand(10)
            return embedding / np.linalg.norm(embedding)
        
        self.resolver = VectorSearchResolver(
            metadata=metadata,
            vector_store_type=VectorStoreType.IN_MEMORY,
            embedding_model_type=EmbeddingModelType.CUSTOM,
            custom_embedder=test_embedder
        )
    
    def asyncSetUp(self):
        """Set up async test environment."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def asyncTearDown(self):
        """Tear down async test environment."""
        self.loop.close()
    
    async def test_health_check(self):
        """Test the health check method."""
        result = await self.resolver.health_check()
        self.assertTrue(result)
    
    def test_can_handle(self):
        """Test can_handle method."""
        # Valid task with resolver specified
        task1 = Task(
            input_data={"operation": "index", "doc_id": "doc1", "content": "Test content"},
            metadata={"resolver": "vector_search"}
        )
        self.assertTrue(self.resolver.can_handle(task1))
        
        # Valid task without resolver specified
        task2 = Task(
            input_data={"operation": "search", "query": "Test query"},
            metadata={}
        )
        self.assertTrue(self.resolver.can_handle(task2))
        
        # Invalid task with different resolver
        task3 = Task(
            input_data={"operation": "index", "doc_id": "doc1", "content": "Test content"},
            metadata={"resolver": "other_resolver"}
        )
        self.assertFalse(self.resolver.can_handle(task3))
        
        # Invalid task with unsupported operation
        task4 = Task(
            input_data={"operation": "unsupported", "doc_id": "doc1"},
            metadata={}
        )
        self.assertFalse(self.resolver.can_handle(task4))
        
        # Invalid task with non-dict input
        task5 = Task(
            input_data="not a dict",
            metadata={}
        )
        self.assertFalse(self.resolver.can_handle(task5))
    
    async def test_handle_index(self):
        """Test index operation."""
        task = Task(
            input_data={
                "operation": "index",
                "doc_id": "doc1",
                "content": "This is a test document for indexing.",
                "metadata": {"category": "test", "priority": "high"}
            }
        )
        
        result = await self.resolver._resolve_task(task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["doc_id"], "doc1")
        self.assertTrue(result.output_data["indexed"])
        self.assertEqual(result.output_data["vector_dimensions"], 10)
        
        # Verify document was indexed
        doc = self.resolver.vector_store.get("doc1")
        self.assertIsNotNone(doc)
        self.assertEqual(doc.content, "This is a test document for indexing.")
        self.assertEqual(doc.metadata["category"], "test")
        self.assertEqual(doc.metadata["priority"], "high")
    
    async def test_handle_search(self):
        """Test search operation."""
        # First index some documents
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "doc1",
                "content": "Artificial intelligence is a field of computer science.",
                "metadata": {"category": "AI"}
            }
        ))
        
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "doc2",
                "content": "Machine learning is a subset of artificial intelligence.",
                "metadata": {"category": "ML"}
            }
        ))
        
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "doc3",
                "content": "Natural language processing deals with text and speech.",
                "metadata": {"category": "NLP"}
            }
        ))
        
        # Now search
        search_task = Task(
            input_data={
                "operation": "search",
                "query": "artificial intelligence and machine learning",
                "top_k": 2
            }
        )
        
        result = await self.resolver._resolve_task(search_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data["results"]), 2)
        self.assertEqual(result.output_data["count"], 2)
        
        # The top result should be either doc1 or doc2
        top_doc_id = result.output_data["results"][0]["doc_id"]
        self.assertIn(top_doc_id, ["doc1", "doc2"])
    
    async def test_handle_search_with_filter(self):
        """Test search operation with metadata filter."""
        # First index some documents
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "doc1",
                "content": "Artificial intelligence is a field of computer science.",
                "metadata": {"category": "AI", "level": "beginner"}
            }
        ))
        
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "doc2",
                "content": "Machine learning is a subset of artificial intelligence.",
                "metadata": {"category": "ML", "level": "intermediate"}
            }
        ))
        
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "doc3",
                "content": "Deep learning uses neural networks with many layers.",
                "metadata": {"category": "DL", "level": "advanced"}
            }
        ))
        
        # Search with filter
        search_task = Task(
            input_data={
                "operation": "search",
                "query": "artificial intelligence",
                "top_k": 3,
                "filter": {"level": "beginner"}
            }
        )
        
        result = await self.resolver._resolve_task(search_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(len(result.output_data["results"]), 1)  # Only one matches the filter
        self.assertEqual(result.output_data["results"][0]["doc_id"], "doc1")
    
    async def test_handle_delete(self):
        """Test delete operation."""
        # First index a document
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "doc1",
                "content": "This is a test document for deletion.",
                "metadata": {"category": "test"}
            }
        ))
        
        # Verify document exists
        self.assertIsNotNone(self.resolver.vector_store.get("doc1"))
        
        # Delete document
        delete_task = Task(
            input_data={
                "operation": "delete",
                "doc_id": "doc1"
            }
        )
        
        result = await self.resolver._resolve_task(delete_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["doc_id"], "doc1")
        self.assertTrue(result.output_data["deleted"])
        
        # Verify document was deleted
        self.assertIsNone(self.resolver.vector_store.get("doc1"))
    
    async def test_handle_get(self):
        """Test get operation."""
        # First index a document
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "doc1",
                "content": "This is a test document for retrieval.",
                "metadata": {"category": "test", "author": "tester"}
            }
        ))
        
        # Get document
        get_task = Task(
            input_data={
                "operation": "get",
                "doc_id": "doc1"
            }
        )
        
        result = await self.resolver._resolve_task(get_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["doc_id"], "doc1")
        self.assertEqual(result.output_data["content"], "This is a test document for retrieval.")
        self.assertEqual(result.output_data["metadata"]["category"], "test")
        self.assertEqual(result.output_data["metadata"]["author"], "tester")
        self.assertEqual(result.output_data["score"], 1.0)
    
    async def test_handle_clear(self):
        """Test clear operation."""
        # First index some documents
        await self.resolver._resolve_task(Task(
            input_data={"operation": "index", "doc_id": "doc1", "content": "Document 1"}
        ))
        
        await self.resolver._resolve_task(Task(
            input_data={"operation": "index", "doc_id": "doc2", "content": "Document 2"}
        ))
        
        # Verify documents exist
        self.assertEqual(self.resolver.vector_store.count(), 2)
        
        # Clear store
        clear_task = Task(
            input_data={"operation": "clear"}
        )
        
        result = await self.resolver._resolve_task(clear_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data["cleared"])
        self.assertEqual(result.output_data["count"], 2)
        
        # Verify store is empty
        self.assertEqual(self.resolver.vector_store.count(), 0)
    
    async def test_handle_count(self):
        """Test count operation."""
        # First index some documents
        await self.resolver._resolve_task(Task(
            input_data={"operation": "index", "doc_id": "doc1", "content": "Document 1"}
        ))
        
        await self.resolver._resolve_task(Task(
            input_data={"operation": "index", "doc_id": "doc2", "content": "Document 2"}
        ))
        
        await self.resolver._resolve_task(Task(
            input_data={"operation": "index", "doc_id": "doc3", "content": "Document 3"}
        ))
        
        # Count documents
        count_task = Task(
            input_data={"operation": "count"}
        )
        
        result = await self.resolver._resolve_task(count_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["count"], 3)
    
    async def test_handle_batch_index(self):
        """Test batch index operation."""
        batch_index_task = Task(
            input_data={
                "operation": "batch_index",
                "documents": [
                    {
                        "doc_id": "batch1",
                        "content": "Batch document 1",
                        "metadata": {"category": "batch", "index": 1}
                    },
                    {
                        "doc_id": "batch2",
                        "content": "Batch document 2",
                        "metadata": {"category": "batch", "index": 2}
                    },
                    {
                        "doc_id": "batch3",
                        "content": "Batch document 3",
                        "metadata": {"category": "batch", "index": 3}
                    }
                ]
            }
        )
        
        result = await self.resolver._resolve_task(batch_index_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["success_count"], 3)
        self.assertEqual(result.output_data["error_count"], 0)
        self.assertEqual(result.output_data["total"], 3)
        
        # Verify documents were indexed
        self.assertEqual(self.resolver.vector_store.count(), 3)
        
        # Verify each document
        for i in range(1, 4):
            doc_id = f"batch{i}"
            doc = self.resolver.vector_store.get(doc_id)
            self.assertIsNotNone(doc)
            self.assertEqual(doc.content, f"Batch document {i}")
            self.assertEqual(doc.metadata["category"], "batch")
            self.assertEqual(doc.metadata["index"], i)
    
    async def test_handle_batch_delete(self):
        """Test batch delete operation."""
        # First index some documents
        batch_index_task = Task(
            input_data={
                "operation": "batch_index",
                "documents": [
                    {"doc_id": "del1", "content": "Delete document 1"},
                    {"doc_id": "del2", "content": "Delete document 2"},
                    {"doc_id": "del3", "content": "Delete document 3"},
                    {"doc_id": "keep1", "content": "Keep document 1"}
                ]
            }
        )
        
        await self.resolver._resolve_task(batch_index_task)
        
        # Verify documents exist
        self.assertEqual(self.resolver.vector_store.count(), 4)
        
        # Batch delete
        batch_delete_task = Task(
            input_data={
                "operation": "batch_delete",
                "doc_ids": ["del1", "del2", "del3", "nonexistent"]
            }
        )
        
        result = await self.resolver._resolve_task(batch_delete_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["deleted_count"], 3)
        self.assertEqual(result.output_data["total"], 4)
        
        # Verify documents were deleted
        self.assertEqual(self.resolver.vector_store.count(), 1)
        self.assertIsNone(self.resolver.vector_store.get("del1"))
        self.assertIsNone(self.resolver.vector_store.get("del2"))
        self.assertIsNone(self.resolver.vector_store.get("del3"))
        self.assertIsNotNone(self.resolver.vector_store.get("keep1"))
    
    async def test_handle_upsert(self):
        """Test upsert operation."""
        # First index a document
        await self.resolver._resolve_task(Task(
            input_data={
                "operation": "index",
                "doc_id": "upsert1",
                "content": "Original content",
                "metadata": {"version": 1}
            }
        ))
        
        # Verify original document
        doc = self.resolver.vector_store.get("upsert1")
        self.assertEqual(doc.content, "Original content")
        self.assertEqual(doc.metadata["version"], 1)
        
        # Upsert document
        upsert_task = Task(
            input_data={
                "operation": "upsert",
                "doc_id": "upsert1",
                "content": "Updated content",
                "metadata": {"version": 2}
            }
        )
        
        result = await self.resolver._resolve_task(upsert_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data["upserted"])
        self.assertTrue(result.output_data["was_update"])
        
        # Verify document was updated
        doc = self.resolver.vector_store.get("upsert1")
        self.assertEqual(doc.content, "Updated content")
        self.assertEqual(doc.metadata["version"], 2)
        
        # Upsert new document
        upsert_new_task = Task(
            input_data={
                "operation": "upsert",
                "doc_id": "upsert2",
                "content": "New document",
                "metadata": {"version": 1}
            }
        )
        
        result = await self.resolver._resolve_task(upsert_new_task)
        
        # Verify result
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.output_data["upserted"])
        self.assertFalse(result.output_data["was_update"])
        
        # Verify new document was added
        doc = self.resolver.vector_store.get("upsert2")
        self.assertEqual(doc.content, "New document")
        self.assertEqual(doc.metadata["version"], 1)
    
    async def test_error_handling(self):
        """Test error handling."""
        # Test missing doc_id
        index_task = Task(
            input_data={
                "operation": "index",
                "content": "Missing doc_id"
            }
        )
        
        result = await self.resolver._resolve_task(index_task)
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "missing_parameter")
        
        # Test missing content
        index_task = Task(
            input_data={
                "operation": "index",
                "doc_id": "doc1"
            }
        )
        
        result = await self.resolver._resolve_task(index_task)
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "missing_parameter")
        
        # Test invalid operation
        invalid_task = Task(
            input_data={
                "operation": "invalid_operation"
            }
        )
        
        result = await self.resolver._resolve_task(invalid_task)
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "invalid_operation")
        
        # Test non-dict input
        non_dict_task = Task(
            input_data="not a dict"
        )
        
        result = await self.resolver._resolve_task(non_dict_task)
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.error.error_type, "invalid_input")


if __name__ == "__main__":
    unittest.main() 