"""
Language Task Resolver Module.

This module provides the LanguageTaskResolver class which handles various language
operations including grammar correction, summarization, translation, sentiment analysis,
and text analysis.
"""
from typing import Any, Dict, List, Optional, Tuple, Union, cast
import re
from enum import Enum
from datetime import datetime

from boss.core.task_models import Task, TaskResult, TaskStatus
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.utils import TaskError  # type: ignore  # Missing stubs


class LanguageOperation:
    """Base class for language operations."""
    
    def __init__(self) -> None:
        """Initialize the language operation."""
        pass
    
    async def process(self, text: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Process the text with the language operation.
        
        Args:
            text: The text to process
            params: Optional parameters for the operation
            
        Returns:
            The processed text result
        """
        raise NotImplementedError("Subclasses must implement this method")


class GrammarCorrector(LanguageOperation):
    """Handles grammar correction operations."""
    
    async def process(self, text: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Correct grammar in the provided text.
        
        Args:
            text: The text to correct
            params: Optional parameters for correction
            
        Returns:
            The corrected text
        """
        # Implement basic grammar correction rules
        corrected = text
        
        # Capitalize first letter of sentences
        corrected = re.sub(r'(^|[.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), corrected)
        
        # Fix common contractions
        contraction_fixes = {
            r'\bi\b': 'I',
            r'\bdont\b': "don't",
            r'\bwont\b': "won't",
            r'\bcant\b': "can't",
            r'\bim\b': "I'm",
            r'\bIve\b': "I've",
            r'\btheyre\b': "they're",
            r'\bweve\b': "we've",
            r'\byoure\b': "you're",
            r'\byoull\b': "you'll",
            r'\bwouldnt\b': "wouldn't",
            r'\bshouldnt\b': "shouldn't",
            r'\bcouldnt\b': "couldn't",
            r'\bhes\b': "he's",
            r'\bshes\b': "she's",
            r'\bits\b': "it's",  # Note: This might cause issues with possessive "its"
            r'\blets\b': "let's",
            r'\bthats\b': "that's",
            r'\bwheres\b': "where's",
            r'\bhows\b': "how's",
            r'\bwhos\b': "who's",
            r'\bwhats\b': "what's"
        }
        
        for pattern, replacement in contraction_fixes.items():
            corrected = re.sub(pattern, replacement, corrected)
        
        # Fix spacing around punctuation
        corrected = re.sub(r'\s+([.,;:!?)])', r'\1', corrected)
        corrected = re.sub(r'([({])\s+', r'\1', corrected)
        
        # Ensure single space after periods, exclamation points, and question marks
        corrected = re.sub(r'([.!?])\s*(\S)', r'\1 \2', corrected)
        
        # Double spaces to single
        corrected = re.sub(r'\s{2,}', ' ', corrected)
        
        return corrected


class Summarizer(LanguageOperation):
    """Handles text summarization operations."""
    
    async def process(self, text: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Summarize the provided text.
        
        Args:
            text: The text to summarize
            params: Optional parameters like max_sentences or percentage
            
        Returns:
            The summarized text
        """
        if not text.strip():
            return ""
        
        params = params or {}
        max_sentences = params.get('max_sentences', 3)
        percentage = params.get('percentage', 0.3)
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        
        if len(sentences) <= max_sentences:
            return text
        
        # Calculate number of sentences to include
        num_sentences = min(max_sentences, max(1, int(len(sentences) * percentage)))
        
        # Simple extractive summarization - just take the first n sentences
        # A more sophisticated approach would use sentence scoring
        summary = ' '.join(sentences[:num_sentences])
        
        return summary


class Translator(LanguageOperation):
    """Handles text translation operations."""
    
    # Simple dictionary of translations for demo purposes
    TRANSLATIONS = {
        ('en', 'es'): {
            'hello': 'hola',
            'world': 'mundo',
            'thank': 'gracias',
            'you': 'tu',
            'please': 'por favor',
            'goodbye': 'adiós',
            'welcome': 'bienvenido',
            'friend': 'amigo',
            'yes': 'sí',
            'no': 'no',
            'good': 'bueno',
            'bad': 'malo',
            'morning': 'mañana',
            'night': 'noche',
            'food': 'comida',
            'water': 'agua',
            'love': 'amor'
        },
        ('es', 'en'): {
            'hola': 'hello',
            'mundo': 'world',
            'gracias': 'thank you',
            'tu': 'you',
            'por favor': 'please',
            'adiós': 'goodbye',
            'bienvenido': 'welcome',
            'amigo': 'friend',
            'sí': 'yes',
            'no': 'no',
            'bueno': 'good',
            'malo': 'bad',
            'mañana': 'morning',
            'noche': 'night',
            'comida': 'food',
            'agua': 'water',
            'amor': 'love'
        }
    }
    
    async def process(self, text: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Translate the provided text.
        
        Args:
            text: The text to translate
            params: Parameters including source_lang and target_lang
            
        Returns:
            The translated text
        """
        if not text.strip():
            return ""
        
        params = params or {}
        source_lang = params.get('source_lang', 'en')
        target_lang = params.get('target_lang', 'es')
        
        language_pair = (source_lang, target_lang)
        
        # Check if we support this language pair
        if language_pair not in self.TRANSLATIONS:
            return f"Unsupported language pair: {source_lang} to {target_lang}"
        
        # Simple word-by-word translation for demo
        words = text.lower().split()
        translated_words = []
        
        for word in words:
            # Remove punctuation for lookup
            clean_word = word.strip('.,;:!?()"\'')
            
            # Translate if in dictionary, otherwise keep original
            translated = self.TRANSLATIONS[language_pair].get(clean_word, clean_word)
            
            # Preserve punctuation
            if word != clean_word:
                # Add back the punctuation
                punctuation = ''.join(c for c in word if c in '.,;:!?()"\'')
                translated += punctuation
            
            translated_words.append(translated)
        
        return ' '.join(translated_words)


class SentimentAnalyzer(LanguageOperation):
    """Handles sentiment analysis operations."""
    
    # Simple dictionaries for demo purposes
    POSITIVE_WORDS = {
        'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
        'superb', 'outstanding', 'awesome', 'terrific', 'happy', 'love',
        'best', 'better', 'positive', 'perfect', 'joy', 'pleased',
        'delighted', 'satisfied', 'impressive', 'exceeds', 'enjoy',
        'like', 'appreciated', 'favorite', 'recommended', 'exceptional'
    }
    
    NEGATIVE_WORDS = {
        'bad', 'terrible', 'awful', 'horrible', 'poor', 'disappointing',
        'worst', 'hate', 'dislike', 'negative', 'sad', 'unhappy',
        'angry', 'annoying', 'frustrating', 'mediocre', 'inadequate',
        'failure', 'fails', 'defective', 'broken', 'useless', 'regret',
        'inferior', 'waste', 'problem', 'complained', 'unacceptable'
    }
    
    INTENSIFIERS = {
        'very', 'extremely', 'incredibly', 'absolutely', 'really',
        'highly', 'completely', 'totally', 'utterly', 'thoroughly'
    }
    
    async def process(self, text: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Analyze the sentiment of the provided text.
        
        Args:
            text: The text to analyze
            params: Optional parameters for the analysis
            
        Returns:
            A string containing the sentiment analysis result
        """
        if not text.strip():
            return "neutral"
        
        # Convert to lowercase and split into words
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Count positive and negative words
        positive_count = 0
        negative_count = 0
        
        # Track if we've seen an intensifier before a sentiment word
        prev_was_intensifier = False
        intensifier_multiplier = 1
        
        for i, word in enumerate(words):
            if word in self.INTENSIFIERS:
                prev_was_intensifier = True
                continue
            
            if prev_was_intensifier:
                intensifier_multiplier = 2
                prev_was_intensifier = False
            else:
                intensifier_multiplier = 1
            
            if word in self.POSITIVE_WORDS:
                positive_count += intensifier_multiplier
            elif word in self.NEGATIVE_WORDS:
                negative_count += intensifier_multiplier
        
        # Calculate sentiment score (-1 to 1)
        total_words = len(words)
        if total_words == 0:
            score = 0.0  # Use float to ensure consistent type
        else:
            # Normalize to range -1 to 1
            score = float((positive_count - negative_count) / total_words)  # Explicit cast to float
        
        # Determine sentiment category
        if score > 0.1:
            strength = "strongly " if score > 0.3 else ""
            return f"{strength}positive (score: {score:.2f})"
        elif score < -0.1:
            strength = "strongly " if score < -0.3 else ""
            return f"{strength}negative (score: {score:.2f})"
        else:
            return f"neutral (score: {score:.2f})"


class TextAnalyzer(LanguageOperation):
    """Handles text analysis operations."""
    
    async def process(self, text: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Analyze the provided text and return various metrics.
        
        Args:
            text: The text to analyze
            params: Optional parameters for the analysis
            
        Returns:
            A string containing the analysis results
        """
        if not text.strip():
            return "{}"
        
        # Count words
        words = re.findall(r'\b\w+\b', text.lower())
        word_count = len(words)
        
        # Count sentences
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sentence_count = len(sentences)
        
        # Count characters (with and without spaces)
        char_count = len(text)
        char_count_no_spaces = len(text.replace(' ', ''))
        
        # Calculate average word length
        avg_word_length = sum(len(word) for word in words) / max(1, word_count)
        
        # Calculate average sentence length
        avg_sentence_length = word_count / max(1, sentence_count)
        
        # Calculate readability (simple Flesch-Kincaid readability score)
        # This is a simplified approximation
        readability_score = 206.835 - 1.015 * (avg_sentence_length) - 84.6 * (avg_word_length / 5)
        
        # Count unique words
        unique_words = len(set(words))
        
        # Assemble the results dictionary
        results = {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "character_count": char_count,
            "character_count_no_spaces": char_count_no_spaces,
            "avg_word_length": round(avg_word_length, 2),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "readability_score": round(readability_score, 2),
            "unique_word_count": unique_words,
            "unique_word_percentage": round(unique_words / max(1, word_count) * 100, 2)
        }
        
        return str(results)


class LanguageTaskResolver(TaskResolver):
    """
    Task resolver for language-specific operations.
    
    Provides various natural language processing operations:
    - Grammar correction
    - Summarization
    - Translation
    - Sentiment analysis
    - Text analysis
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the language task resolver."""
        super().__init__(metadata)
        self._operations = {
            "grammar_correction": GrammarCorrector(),
            "summarize": Summarizer(),
            "translate": Translator(),
            "sentiment_analysis": SentimentAnalyzer(),
            "text_analysis": TextAnalyzer()
        }
    
    async def health_check(self) -> bool:
        """
        Check if the resolver is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        # For a more robust implementation, this would check the health
        # of any external NLP services being used
        return True
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a language-related task.
        
        Args:
            task: The task to resolve
            
        Returns:
            The task result
        """
        # Extract operation and text from task input
        try:
            operation_name = task.input_data.get("operation")
            if not operation_name:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message="Missing 'operation' in task input",
                    output_data={}
                )
            
            text = task.input_data.get("text", "")
            params = task.input_data.get("params", {})
            
            if operation_name not in self._operations:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    message=f"Unknown operation: {operation_name}",
                    output_data={}
                )
            
            # Process the operation
            operation = self._operations[operation_name]
            result = await operation.process(text, params)
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                message=f"Successfully completed {operation_name} operation",
                output_data={"result": result}
            )
        
        except TaskError as e:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=str(e),
                output_data={}
            )
        except Exception as e:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"An error occurred during {operation_name if 'operation_name' in locals() else 'language'} operation: {str(e)}",
                output_data={}
            )
    
    async def _handle_language_operation(self, task: Task) -> TaskResult:
        """
        Handle a language operation task.
        
        Args:
            task: The task to handle
            
        Returns:
            The task result
        """
        return await self.resolve(task) 