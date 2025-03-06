"""
Test module for the API client.
"""

import unittest
from unittest.mock import MagicMock, patch

from boss_py_agent.utils.api_client import ClaudeAPIClient


class TestClaudeAPIClient(unittest.TestCase):
    """Test the Claude API client."""

    def setUp(self):
        """Set up test case."""
        self.api_key = "test_api_key"
        # Default model matching the one in api_client.py
        self.model = "claude-3-7-sonnet-20240229"
        self.test_prompt = "Test prompt"
        self.test_system_prompt = "You are a helpful assistant"

    def test_initialization(self):
        """Test client initialization."""
        client = ClaudeAPIClient(
            api_key=self.api_key,
            model=self.model,
            max_retries=5,
            retry_delay=2.0,
        )

        self.assertEqual(client.api_key, self.api_key)
        self.assertEqual(client.model, self.model)
        self.assertEqual(client.max_retries, 5)
        self.assertEqual(client.retry_delay, 2.0)
        self.assertIsNone(client.api_url)

    @patch("boss_py_agent.utils.api_client.anthropic.Anthropic")
    def test_generate_text_success(self, mock_anthropic_class):
        """Test successful text generation."""
        # Setup mock
        mock_anthropic_instance = mock_anthropic_class.return_value
        mock_messages = MagicMock()
        mock_anthropic_instance.messages = mock_messages

        # Create mock message response
        mock_content = MagicMock()
        mock_content.text = "Generated text"
        mock_message = MagicMock()
        mock_message.content = [mock_content]
        mock_messages.create.return_value = mock_message

        # Create client
        client = ClaudeAPIClient(api_key=self.api_key)

        # Call generate_text
        result = client.generate_text(
            prompt="Test prompt",
            system_prompt="You are a helpful assistant",
            max_tokens=1000,
            temperature=0.5
        )

        # Verify the result
        self.assertEqual(result, "Generated text")

        # Verify the client was called with correct parameters
        mock_messages.create.assert_called_once()
        call_args = mock_messages.create.call_args[1]
        # Using the updated model name
        self.assertEqual(call_args["model"], self.model)
        self.assertEqual(call_args["max_tokens"], 1000)
        self.assertEqual(call_args["temperature"], 0.5)

    @patch("boss_py_agent.utils.api_client.anthropic.Anthropic")
    def test_generate_text_retry_success(self, mock_anthropic_class):
        """Test successful retry after initial failure."""
        # Setup mock
        mock_anthropic_instance = mock_anthropic_class.return_value
        mock_messages = MagicMock()
        mock_anthropic_instance.messages = mock_messages

        # First call raises an exception, second call succeeds
        mock_content = MagicMock()
        mock_content.text = "Generated text after retry"
        mock_message = MagicMock()
        mock_message.content = [mock_content]
        
        # Configure the mock to raise an exception on first call, then succeed
        mock_messages.create.side_effect = [
            Exception("API error"),
            mock_message
        ]

        # Create client with retry
        client = ClaudeAPIClient(
            api_key=self.api_key,
            max_retries=2,
            retry_delay=0.01  # Short delay for testing
        )

        # Call generate_text
        result = client.generate_text(prompt="Test prompt")

        # Verify the result
        self.assertEqual(result, "Generated text after retry")
        self.assertEqual(mock_messages.create.call_count, 2)

    @patch("boss_py_agent.utils.api_client.anthropic.Anthropic")
    def test_generate_text_retry_exhausted(self, mock_anthropic_class):
        """Test exception when all retries are exhausted."""
        # Setup mock
        mock_anthropic_instance = mock_anthropic_class.return_value
        mock_messages = MagicMock()
        mock_anthropic_instance.messages = mock_messages

        # Always raise an exception
        mock_messages.create.side_effect = Exception("API error")

        # Create client with retry
        client = ClaudeAPIClient(
            api_key=self.api_key,
            max_retries=2,
            retry_delay=0.01  # Short delay for testing
        )

        # Call generate_text
        with self.assertRaises(Exception) as context:
            client.generate_text(prompt="Test prompt")

        self.assertIn("Claude API failed", str(context.exception))
        # Initial + 2 retries
        self.assertEqual(mock_messages.create.call_count, 3)


if __name__ == "__main__":
    unittest.main() 