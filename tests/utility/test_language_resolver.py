"""
Unit tests for the LanguageTaskResolver.

This module contains tests for the LanguageTaskResolver class
and its various language operations.
"""
import unittest
import asyncio
from typing import Dict, Any, List

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.utility.language_resolver import (
    LanguageTaskResolver,
    GrammarCorrector,
    Summarizer,
    Translator,
    SentimentAnalyzer,
    TextAnalyzer,
    LanguageOperation
)


class TestLanguageOperation(unittest.IsolatedAsyncioTestCase):
    """Base tests for language operations."""
    
    async def test_base_language_operation(self) -> None:
        """Test that the base class cannot be instantiated directly."""
        operation = LanguageOperation("test", "Test operation")
        
        with self.assertRaises(NotImplementedError):
            await operation.process("Test text", {})


class TestGrammarCorrector(unittest.IsolatedAsyncioTestCase):
    """Tests for the GrammarCorrector operation."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.corrector = GrammarCorrector()
    
    async def test_grammar_corrections(self) -> None:
        """Test basic grammar corrections."""
        tests = [
            ("i am a test", "I am a test"),
            ("i'm happy", "I'm happy"),
            ("dont worry", "don't worry"),
            ("theres a bug", "there's a bug"),
            ("text with  multiple   spaces", "text with multiple spaces"),
            ("text with a space before a comma , fix it", "text with a space before a comma, fix it"),
            ("sentences without caps. another sentence.", "Sentences without caps. Another sentence.")
        ]
        
        for input_text, expected in tests:
            result = await self.corrector.process(input_text, {})
            self.assertEqual(result, expected)


class TestSummarizer(unittest.IsolatedAsyncioTestCase):
    """Tests for the Summarizer operation."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.summarizer = Summarizer()
    
    async def test_summarization(self) -> None:
        """Test basic summarization."""
        # Test with a short text that shouldn't be summarized
        short_text = "This is a short text. It should not be summarized."
        short_result = await self.summarizer.process(short_text, {})
        self.assertEqual(short_result, short_text)
        
        # Test with a longer text
        long_text = """
        Natural language processing (NLP) is a subfield of linguistics, computer science, and artificial intelligence.
        It focuses on the interactions between computers and human language.
        NLP is used to analyze, understand, and generate human language in a valuable way.
        The field has seen rapid progress in recent years due to advances in machine learning.
        Modern NLP applications include machine translation, sentiment analysis, and chatbots.
        These systems are becoming increasingly sophisticated and can understand context and nuance.
        However, NLP still faces challenges with understanding sarcasm, humor, and cultural references.
        Researchers continue to develop new approaches to make NLP systems more human-like in their understanding.
        The future of NLP looks promising as models continue to improve and find new applications.
        """
        
        summary = await self.summarizer.process(long_text, {"max_sentences": 3})
        
        # The summary should be shorter than the original
        self.assertLess(len(summary), len(long_text))
        
        # The summary should have at most 3 sentences
        sentences = summary.split(". ")
        self.assertLessEqual(len(sentences), 3)


class TestTranslator(unittest.IsolatedAsyncioTestCase):
    """Tests for the Translator operation."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.translator = Translator()
    
    async def test_translation(self) -> None:
        """Test basic translation."""
        # Test English to Spanish
        en_text = "hello world thank you"
        es_result = await self.translator.process(en_text, {"source_lang": "en", "target_lang": "es"})
        self.assertEqual(es_result, "hola mundo gracias")
        
        # Test Spanish to English
        es_text = "hola mundo gracias"
        en_result = await self.translator.process(es_text, {"source_lang": "es", "target_lang": "en"})
        self.assertEqual(en_result, "hello world thank you")
        
        # Test unsupported language pair
        unsupported = await self.translator.process("test", {"source_lang": "fr", "target_lang": "de"})
        self.assertTrue(unsupported.startswith("Translation not supported"))


class TestSentimentAnalyzer(unittest.IsolatedAsyncioTestCase):
    """Tests for the SentimentAnalyzer operation."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.analyzer = SentimentAnalyzer()
    
    async def test_sentiment_analysis(self) -> None:
        """Test sentiment analysis."""
        # Test positive sentiment
        positive_text = "This is a great product. I love it. It's amazing and fantastic."
        positive_result = await self.analyzer.process(positive_text, {})
        self.assertIn("'sentiment': 'positive'", positive_result)
        
        # Test negative sentiment
        negative_text = "This is terrible. I hate it. It's the worst product ever."
        negative_result = await self.analyzer.process(negative_text, {})
        self.assertIn("'sentiment': 'negative'", negative_result)
        
        # Test neutral sentiment
        neutral_text = "This is a product. It exists. Here are some facts about it."
        neutral_result = await self.analyzer.process(neutral_text, {})
        self.assertIn("'sentiment': 'neutral'", neutral_result)
        
        # Test intensifiers
        intensified_text = "This is a very good product."
        intensified_result = await self.analyzer.process(intensified_text, {})
        self.assertIn("'sentiment': 'positive'", intensified_result)


class TestTextAnalyzer(unittest.IsolatedAsyncioTestCase):
    """Tests for the TextAnalyzer operation."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.analyzer = TextAnalyzer()
    
    async def test_text_analysis(self) -> None:
        """Test text analysis."""
        text = "This is a sample text. It has two sentences. The sentences are short."
        
        result = await self.analyzer.process(text, {})
        
        # Check that the result contains the expected keys
        self.assertIn("'word_count':", result)
        self.assertIn("'sentence_count':", result)
        self.assertIn("'avg_word_length':", result)
        self.assertIn("'avg_sentence_length':", result)
        self.assertIn("'reading_level':", result)
        
        # Check some specific values
        self.assertIn("'sentence_count': 3", result)
        
        # Empty text should handle gracefully
        empty_result = await self.analyzer.process("", {})
        self.assertIn("'word_count': 0", empty_result)


class TestLanguageTaskResolver(unittest.IsolatedAsyncioTestCase):
    """Tests for the LanguageTaskResolver class."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.resolver = LanguageTaskResolver(
            metadata=TaskResolverMetadata(
                name="LanguageTaskResolver",
                version="1.0.0",
                description="Test language resolver"
            )
        )
    
    async def test_health_check(self) -> None:
        """Test health check functionality."""
        health_status = await self.resolver.health_check()
        self.assertTrue(health_status)
    
    def test_can_handle(self) -> None:
        """Test can_handle functionality."""
        # Test with valid operations
        for operation in ["grammar_correction", "summarize", "translate", 
                          "sentiment_analysis", "text_analysis"]:
            task = Task(
                name="test_task",
                input_data={"operation": operation}
            )
            self.assertTrue(self.resolver.can_handle(task))
        
        # Test with invalid operation
        task = Task(
            name="test_task",
            input_data={"operation": "invalid_operation"}
        )
        self.assertFalse(self.resolver.can_handle(task))
        
        # Test with no operation
        task = Task(
            name="test_task"
        )
        self.assertFalse(self.resolver.can_handle(task))
    
    async def test_grammar_correction_task(self) -> None:
        """Test grammar correction task."""
        task = Task(
            name="grammar_correction_task",
            input_data={
                "operation": "grammar_correction",
                "text": "i am testing this. dont forget to check it."
            }
        )
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["operation"], "grammar_correction")
        self.assertEqual(result.output_data["result"], "I am testing this. Don't forget to check it.")
    
    async def test_summarize_task(self) -> None:
        """Test summarization task."""
        task = Task(
            name="summarize_task",
            input_data={
                "operation": "summarize",
                "text": """
                Natural language processing (NLP) is a subfield of linguistics, computer science, and artificial intelligence.
                It focuses on the interactions between computers and human language.
                NLP is used to analyze, understand, and generate human language in a valuable way.
                The field has seen rapid progress in recent years due to advances in machine learning.
                Modern NLP applications include machine translation, sentiment analysis, and chatbots.
                """
            }
        )
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["operation"], "summarize")
        self.assertIsInstance(result.output_data["result"], str)
    
    async def test_translate_task(self) -> None:
        """Test translation task."""
        task = Task(
            name="translate_task",
            input_data={
                "operation": "translate",
                "text": "hello world",
                "params": {
                    "source_lang": "en",
                    "target_lang": "es"
                }
            }
        )
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["operation"], "translate")
        self.assertEqual(result.output_data["result"], "hola mundo")
    
    async def test_sentiment_analysis_task(self) -> None:
        """Test sentiment analysis task."""
        task = Task(
            name="sentiment_analysis_task",
            input_data={
                "operation": "sentiment_analysis",
                "text": "This is a great product. I love it."
            }
        )
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["operation"], "sentiment_analysis")
        self.assertIn("'sentiment': 'positive'", result.output_data["result"])
    
    async def test_text_analysis_task(self) -> None:
        """Test text analysis task."""
        task = Task(
            name="text_analysis_task",
            input_data={
                "operation": "text_analysis",
                "text": "This is a sample text. It has multiple sentences. The sentences are not too complex."
            }
        )
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data["operation"], "text_analysis")
        self.assertIn("'word_count':", result.output_data["result"])
    
    async def test_missing_operation(self) -> None:
        """Test with missing operation."""
        task = Task(
            name="missing_operation_task",
            input_data={
                "text": "This is a test."
            }
        )
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.message, "Missing operation parameter")
    
    async def test_missing_text(self) -> None:
        """Test with missing text."""
        task = Task(
            name="missing_text_task",
            input_data={
                "operation": "grammar_correction"
            }
        )
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.message, "Missing text parameter")
    
    async def test_unknown_operation(self) -> None:
        """Test with unknown operation."""
        task = Task(
            name="unknown_operation_task",
            input_data={
                "operation": "unknown_operation",
                "text": "This is a test."
            }
        )
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertEqual(result.message, "Unknown operation: unknown_operation")


if __name__ == "__main__":
    unittest.main() 