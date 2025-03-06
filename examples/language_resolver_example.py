"""
Example demonstrating the use of LanguageTaskResolver.

This script showcases various language operations provided by the 
LanguageTaskResolver, including grammar correction, summarization, 
translation, sentiment analysis, and text analysis.
"""
import asyncio
import json
from datetime import datetime

from boss.core.task_models import Task
from boss.core.task_resolver import TaskResolverMetadata
from boss.utility.language_resolver import LanguageTaskResolver


async def main():
    """Run language resolver examples."""
    print("====== LanguageTaskResolver Example ======")
    
    # Create the resolver
    resolver = LanguageTaskResolver(
        metadata=TaskResolverMetadata(
            name="LanguageTaskResolver",
            version="1.0.0",
            description="Handles language-specific operations"
        )
    )
    
    # Check health
    print("\n[Health Check]")
    health_status = await resolver.health_check()
    print(f"Resolver is {'healthy' if health_status else 'unhealthy'}")
    
    # Example 1: Grammar Correction
    print("\n[Example 1: Grammar Correction]")
    grammar_task = Task(
        name="grammar_correction_example",
        input_data={
            "operation": "grammar_correction",
            "text": "i am writing this example to show grammar correction. dont forget to try it!"
        }
    )
    
    grammar_result = await resolver.resolve(grammar_task)
    print(f"Original: {grammar_task.input_data['text']}")
    print(f"Corrected: {grammar_result.output_data['result']}")
    
    # Example 2: Text Summarization
    print("\n[Example 2: Text Summarization]")
    long_text = """
    Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to the natural intelligence displayed by animals including humans.
    AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and takes actions that maximize its chance of achieving its goals.
    The term "artificial intelligence" had previously been used to describe machines that mimic and display "human" cognitive skills that are associated with the human mind, such as "learning" and "problem-solving".
    This definition has since been rejected by major AI researchers who now describe AI in terms of rationality and acting rationally, which does not limit how intelligence can be articulated.
    AI applications include advanced web search engines, recommendation systems, understanding human speech, self-driving cars, generative or creative tools, automated decision-making, and competing at the highest level in strategic game systems.
    As machines become increasingly capable, tasks considered to require "intelligence" are often removed from the definition of AI, a phenomenon known as the AI effect.
    For instance, optical character recognition is frequently excluded from things considered to be AI, having become a routine technology.
    """
    
    summarize_task = Task(
        name="summarize_example",
        input_data={
            "operation": "summarize",
            "text": long_text,
            "params": {
                "max_sentences": 3,
                "percentage": 0.3
            }
        }
    )
    
    summarize_result = await resolver.resolve(summarize_task)
    print(f"Original length: {len(long_text)} characters")
    print(f"Summary length: {len(summarize_result.output_data['result'])} characters")
    print(f"Summary:\n{summarize_result.output_data['result']}")
    
    # Example 3: Translation
    print("\n[Example 3: Translation]")
    translate_task = Task(
        name="translate_example",
        input_data={
            "operation": "translate",
            "text": "hello world thank you please",
            "params": {
                "source_lang": "en",
                "target_lang": "es"
            }
        }
    )
    
    translate_result = await resolver.resolve(translate_task)
    print(f"English: {translate_task.input_data['text']}")
    print(f"Spanish: {translate_result.output_data['result']}")
    
    # Example 4: Sentiment Analysis
    print("\n[Example 4: Sentiment Analysis]")
    
    # Positive text
    positive_text = "I love this product! It's amazing and has exceeded all my expectations. The quality is excellent."
    sentiment_task = Task(
        name="sentiment_example_positive",
        input_data={
            "operation": "sentiment_analysis",
            "text": positive_text
        }
    )
    
    sentiment_result = await resolver.resolve(sentiment_task)
    print(f"Text: {positive_text}")
    print(f"Analysis: {sentiment_result.output_data['result']}")
    
    # Negative text
    negative_text = "This is terrible. I hate it and regret purchasing. The quality is poor and it doesn't work as advertised."
    sentiment_task = Task(
        name="sentiment_example_negative",
        input_data={
            "operation": "sentiment_analysis",
            "text": negative_text
        }
    )
    
    sentiment_result = await resolver.resolve(sentiment_task)
    print(f"\nText: {negative_text}")
    print(f"Analysis: {sentiment_result.output_data['result']}")
    
    # Example 5: Text Analysis
    print("\n[Example 5: Text Analysis]")
    sample_text = """
    This is a sample text to analyze. It contains several sentences of varying length and complexity.
    Some sentences are short. Others are more complex and contain multiple clauses, which can affect
    the readability score and other metrics that the text analyzer will calculate based on the input
    provided to it through the task resolver interface.
    """
    
    analysis_task = Task(
        name="text_analysis_example",
        input_data={
            "operation": "text_analysis",
            "text": sample_text
        }
    )
    
    analysis_result = await resolver.resolve(analysis_task)
    
    # Format the result as JSON for better readability
    try:
        result_str = analysis_result.output_data['result']
        # Convert string representation of dict to actual dict
        result_dict = eval(result_str)
        print(f"Text Analysis Results:\n{json.dumps(result_dict, indent=2)}")
    except:
        print(f"Text Analysis Results:\n{analysis_result.output_data['result']}")
    
    # Example 6: Error handling
    print("\n[Example 6: Error Handling]")
    error_task = Task(
        name="error_example",
        input_data={
            "operation": "unknown_operation",
            "text": "This will cause an error."
        }
    )
    
    error_result = await resolver.resolve(error_task)
    print(f"Status: {error_result.status}")
    print(f"Error Message: {error_result.message}")


if __name__ == "__main__":
    asyncio.run(main()) 