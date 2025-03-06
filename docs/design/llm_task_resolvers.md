# LLM-Based TaskResolvers

## Overview

LLM-based TaskResolvers are specialized TaskResolvers that use Large Language Models to process tasks. These resolvers form the foundation for many advanced capabilities in the BOSS system, enabling natural language processing, code generation, reasoning, and more.

## Supported LLM Providers

The BOSS system integrates with multiple LLM providers:

1. **OpenAI** - GPT models (GPT-4, GPT-3.5-Turbo)
2. **Anthropic** - Claude models (Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku)
3. **Together AI** - Various models including open-source models

## Base LLM TaskResolver

All LLM-based TaskResolvers inherit from a common base class:

```python
class BaseLLMTaskResolver(TaskResolver):
    """
    Base class for all LLM-based TaskResolvers.
    """
    name = "BaseLLMResolver"
    description = "Base resolver for LLM interactions"
    version = "1.0.0"
    depth = 1
    evolution_strategy = "Evolve by improving prompts or switching to better models"
    
    input_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "parameters": {
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "max_tokens": {"type": "integer", "minimum": 1},
                    "model": {"type": "string"}
                }
            }
        },
        "required": ["prompt"]
    }
    
    result_schema = {
        "type": "object",
        "properties": {
            "response": {"type": "string"},
            "model_used": {"type": "string"},
            "usage": {
                "type": "object",
                "properties": {
                    "prompt_tokens": {"type": "integer"},
                    "completion_tokens": {"type": "integer"},
                    "total_tokens": {"type": "integer"}
                }
            }
        }
    }
    
    error_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"},
            "provider": {"type": "string"}
        }
    }
    
    @abstractmethod
    async def generate_text(self, prompt: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate text from the LLM based on the prompt and parameters.
        Returns a dict with response, model_used, and usage information.
        """
        pass
    
    async def resolve(self, task: Task) -> Task:
        """
        Resolve the task by calling the LLM.
        """
        task.status = TaskStatus.IN_PROGRESS
        
        try:
            prompt = task.input_data["prompt"]
            parameters = task.input_data.get("parameters", {})
            
            result = await self.generate_text(prompt, parameters)
            
            task.result = TaskResult(data=result)
            task.status = TaskStatus.COMPLETED
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = TaskError(
                code="llm_error",
                message=str(e),
                details={"traceback": traceback.format_exc()}
            )
            
        return task
```

## OpenAI TaskResolver

```python
class OpenAITaskResolver(BaseLLMTaskResolver):
    """
    TaskResolver for OpenAI models (GPT-4, GPT-3.5-Turbo).
    """
    name = "OpenAIResolver"
    description = "Resolver for OpenAI GPT models"
    version = "1.0.0"
    
    def __init__(self, api_key: str = None):
        """
        Initialize the OpenAI client.
        If api_key is not provided, it will be loaded from environment variables.
        """
        from openai import OpenAI
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided and not found in environment variables")
            
        self.client = OpenAI(api_key=self.api_key)
    
    async def generate_text(self, prompt: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate text using OpenAI models.
        """
        model = parameters.get("model", "gpt-3.5-turbo")
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return {
            "response": response.choices[0].message.content,
            "model_used": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    
    def health_check(self) -> bool:
        """
        Check if the OpenAI API is accessible.
        """
        try:
            # Simple model call to check health
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello, are you operational?"}],
                max_tokens=5
            )
            return response.choices[0].message.content is not None
        except Exception:
            return False
```

## Anthropic TaskResolver

```python
class AnthropicTaskResolver(BaseLLMTaskResolver):
    """
    TaskResolver for Anthropic Claude models.
    """
    name = "AnthropicResolver"
    description = "Resolver for Anthropic Claude models"
    version = "1.0.0"
    
    def __init__(self, api_key: str = None):
        """
        Initialize the Anthropic client.
        If api_key is not provided, it will be loaded from environment variables.
        """
        import anthropic
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key not provided and not found in environment variables")
            
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    async def generate_text(self, prompt: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate text using Anthropic Claude models.
        """
        model = parameters.get("model", "claude-3-sonnet-20240229")
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        
        response = await asyncio.to_thread(
            self.client.messages.create,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return {
            "response": response.content[0].text,
            "model_used": model,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }
    
    def health_check(self) -> bool:
        """
        Check if the Anthropic API is accessible.
        """
        try:
            # Simple model call to check health
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hello, are you operational?"}],
                max_tokens=5
            )
            return response.content[0].text is not None
        except Exception:
            return False
```

## Together AI TaskResolver

```python
class TogetherAITaskResolver(BaseLLMTaskResolver):
    """
    TaskResolver for Together AI models.
    """
    name = "TogetherAIResolver"
    description = "Resolver for models hosted on Together AI"
    version = "1.0.0"
    
    def __init__(self, api_key: str = None, api_url: str = None, timeout: int = None):
        """
        Initialize the Together AI client.
        If parameters are not provided, they will be loaded from environment variables.
        """
        import requests
        
        self.api_key = api_key or os.getenv("TOGETHER_API_KEY")
        if not self.api_key:
            raise ValueError("Together AI API key not provided and not found in environment variables")
            
        self.api_url = api_url or os.getenv("TOGETHER_API_URL", "https://api.together.xyz/v1")
        self.timeout = timeout or int(os.getenv("TOGETHER_API_TIMEOUT", "120"))
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    async def generate_text(self, prompt: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate text using Together AI models.
        """
        model = parameters.get("model", "mistralai/Mixtral-8x7B-Instruct-v0.1")
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async def make_request():
            response = await asyncio.to_thread(
                self.session.post,
                f"{self.api_url}/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        
        response_data = await make_request()
        
        return {
            "response": response_data["choices"][0]["message"]["content"],
            "model_used": model,
            "usage": {
                "prompt_tokens": response_data["usage"]["prompt_tokens"],
                "completion_tokens": response_data["usage"]["completion_tokens"],
                "total_tokens": response_data["usage"]["total_tokens"]
            }
        }
    
    def health_check(self) -> bool:
        """
        Check if the Together AI API is accessible.
        """
        try:
            payload = {
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "messages": [{"role": "user", "content": "Hello, are you operational?"}],
                "max_tokens": 5
            }
            
            response = self.session.post(
                f"{self.api_url}/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"] is not None
        except Exception:
            return False
```

## Specialized LLM TaskResolvers

Beyond the basic LLM TaskResolvers, we can create specialized versions for specific tasks:

### CodeGenerationResolver

```python
class CodeGenerationResolver(OpenAITaskResolver):
    """
    TaskResolver for generating code using OpenAI models.
    """
    name = "CodeGenerationResolver"
    description = "Generates code based on requirements"
    version = "1.0.0"
    
    input_schema = {
        "type": "object",
        "properties": {
            "language": {"type": "string"},
            "requirements": {"type": "string"},
            "context": {"type": "string", "optional": True},
            "parameters": {
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "model": {"type": "string"}
                }
            }
        },
        "required": ["language", "requirements"]
    }
    
    result_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "explanation": {"type": "string"},
            "model_used": {"type": "string"},
            "usage": {
                "type": "object",
                "properties": {
                    "prompt_tokens": {"type": "integer"},
                    "completion_tokens": {"type": "integer"},
                    "total_tokens": {"type": "integer"}
                }
            }
        }
    }
    
    async def resolve(self, task: Task) -> Task:
        """
        Resolve the task by generating code.
        """
        task.status = TaskStatus.IN_PROGRESS
        
        try:
            language = task.input_data["language"]
            requirements = task.input_data["requirements"]
            context = task.input_data.get("context", "")
            parameters = task.input_data.get("parameters", {})
            
            if "model" not in parameters:
                parameters["model"] = "gpt-4"  # Default to GPT-4 for code generation
                
            prompt = f"""
            Please generate {language} code based on the following requirements:
            
            {requirements}
            
            {"Additional context:" if context else ""}
            {context if context else ""}
            
            Please provide only the functional code without explanations within the code block.
            After the code block, please provide a brief explanation of how the code works.
            """
            
            result = await self.generate_text(prompt, parameters)
            
            # Extract code and explanation from the response
            content = result["response"]
            code_pattern = r"```[\w]*\n(.*?)```"
            code_match = re.search(code_pattern, content, re.DOTALL)
            
            if code_match:
                code = code_match.group(1).strip()
                explanation = content.split("```")[-1].strip()
            else:
                code = content
                explanation = "No separate explanation provided."
            
            task.result = TaskResult(data={
                "code": code,
                "explanation": explanation,
                "model_used": result["model_used"],
                "usage": result["usage"]
            })
            task.status = TaskStatus.COMPLETED
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = TaskError(
                code="code_generation_error",
                message=str(e),
                details={"traceback": traceback.format_exc()}
            )
            
        return task
```

### TextAnalysisResolver

```python
class TextAnalysisResolver(AnthropicTaskResolver):
    """
    TaskResolver for analyzing text using Anthropic Claude models.
    """
    name = "TextAnalysisResolver"
    description = "Analyzes text for sentiment, entities, and themes"
    version = "1.0.0"
    
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "analysis_type": {"type": "string", "enum": ["sentiment", "entities", "themes", "all"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "model": {"type": "string"}
                }
            }
        },
        "required": ["text", "analysis_type"]
    }
    
    result_schema = {
        "type": "object",
        "properties": {
            "analysis": {"type": "object"},
            "model_used": {"type": "string"},
            "usage": {
                "type": "object",
                "properties": {
                    "prompt_tokens": {"type": "integer"},
                    "completion_tokens": {"type": "integer"},
                    "total_tokens": {"type": "integer"}
                }
            }
        }
    }
    
    async def resolve(self, task: Task) -> Task:
        """
        Resolve the task by analyzing text.
        """
        task.status = TaskStatus.IN_PROGRESS
        
        try:
            text = task.input_data["text"]
            analysis_type = task.input_data["analysis_type"]
            parameters = task.input_data.get("parameters", {})
            
            if "model" not in parameters:
                parameters["model"] = "claude-3-opus-20240229"  # Default to Claude 3 Opus for analysis
                
            prompt = f"""
            Please analyze the following text for {analysis_type}:
            
            {text}
            
            Provide your analysis in JSON format with the following structure:
            
            ```json
            {{
              "analysis_type": "{analysis_type}",
              "results": {{
                // Analysis results here
              }}
            }}
            ```
            """
            
            result = await self.generate_text(prompt, parameters)
            
            # Extract JSON from the response
            content = result["response"]
            json_pattern = r"```json\s*(.*?)\s*```"
            json_match = re.search(json_pattern, content, re.DOTALL)
            
            if json_match:
                analysis_json = json.loads(json_match.group(1))
            else:
                # Try to find any JSON in the response
                json_pattern = r"({[\s\S]*})"
                json_match = re.search(json_pattern, content)
                if json_match:
                    analysis_json = json.loads(json_match.group(1))
                else:
                    analysis_json = {"error": "Could not parse JSON from response", "raw_response": content}
            
            task.result = TaskResult(data={
                "analysis": analysis_json,
                "model_used": result["model_used"],
                "usage": result["usage"]
            })
            task.status = TaskStatus.COMPLETED
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = TaskError(
                code="text_analysis_error",
                message=str(e),
                details={"traceback": traceback.format_exc()}
            )
            
        return task
```

## Factory Pattern for LLM TaskResolvers

To simplify the creation and use of LLM TaskResolvers, we can implement a factory pattern:

```python
class LLMTaskResolverFactory:
    """
    Factory for creating LLM TaskResolvers.
    """
    
    @staticmethod
    def create_resolver(provider: str, **kwargs) -> BaseLLMTaskResolver:
        """
        Create an LLM TaskResolver for the specified provider.
        
        Args:
            provider: The LLM provider ("openai", "anthropic", "together")
            **kwargs: Additional arguments to pass to the resolver constructor
            
        Returns:
            An instance of the appropriate LLM TaskResolver
        """
        provider = provider.lower()
        
        if provider == "openai":
            return OpenAITaskResolver(**kwargs)
        elif provider == "anthropic":
            return AnthropicTaskResolver(**kwargs)
        elif provider == "together":
            return TogetherAITaskResolver(**kwargs)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    
    @staticmethod
    def create_specialized_resolver(resolver_type: str, **kwargs) -> BaseLLMTaskResolver:
        """
        Create a specialized LLM TaskResolver.
        
        Args:
            resolver_type: The type of specialized resolver
            **kwargs: Additional arguments to pass to the resolver constructor
            
        Returns:
            An instance of the appropriate specialized LLM TaskResolver
        """
        resolver_type = resolver_type.lower()
        
        if resolver_type == "code_generation":
            return CodeGenerationResolver(**kwargs)
        elif resolver_type == "text_analysis":
            return TextAnalysisResolver(**kwargs)
        else:
            raise ValueError(f"Unknown specialized resolver type: {resolver_type}")
```

## Main Entry Point for Testing LLM TaskResolvers

Each LLM TaskResolver includes a main entry point for testing and health checks:

```python
def main():
    """
    Main entry point for testing the LLM TaskResolvers.
    """
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create resolvers
    factory = LLMTaskResolverFactory()
    openai_resolver = factory.create_resolver("openai")
    anthropic_resolver = factory.create_resolver("anthropic")
    together_resolver = factory.create_resolver("together")
    
    # Test resolvers
    async def test_resolvers():
        print("Testing OpenAI Resolver...")
        openai_healthy = openai_resolver.health_check()
        print(f"Health check: {'PASSED' if openai_healthy else 'FAILED'}")
        
        print("\nTesting Anthropic Resolver...")
        anthropic_healthy = anthropic_resolver.health_check()
        print(f"Health check: {'PASSED' if anthropic_healthy else 'FAILED'}")
        
        print("\nTesting Together AI Resolver...")
        together_healthy = together_resolver.health_check()
        print(f"Health check: {'PASSED' if together_healthy else 'FAILED'}")
        
        # Test with a sample task
        if openai_healthy:
            task = Task(
                id="test-task",
                description="Test OpenAI completion",
                input_data={
                    "prompt": "What are the benefits of microservices architecture?",
                    "parameters": {
                        "model": "gpt-3.5-turbo",
                        "temperature": 0.7,
                        "max_tokens": 200
                    }
                },
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            print("\nSending task to OpenAI Resolver...")
            result_task = await openai_resolver.resolve(task)
            
            if result_task.status == TaskStatus.COMPLETED:
                print(f"\nResult:\n{result_task.result.data['response']}")
                print(f"\nTokens used: {result_task.result.data['usage']['total_tokens']}")
            else:
                print(f"\nError: {result_task.error.message}")
    
    # Run the test
    asyncio.run(test_resolvers())

if __name__ == "__main__":
    main() 