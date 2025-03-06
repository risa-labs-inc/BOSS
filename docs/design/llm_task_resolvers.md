# LLM-Based TaskResolvers

## Overview

LLM-based TaskResolvers are specialized TaskResolvers that use Large Language Models to process tasks. These resolvers form the foundation for many advanced capabilities in the BOSS system, enabling natural language processing, code generation, reasoning, and more.

## Supported LLM Providers

The BOSS system integrates with multiple LLM providers:

1. **OpenAI** - GPT models (GPT-4o, GPT-4 Turbo, GPT-3.5-Turbo)
2. **Anthropic** - Claude models (Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku)
3. **Together AI** - Various models including Llama-3, Mistral, and other open-source models
4. **xAI** - Grok models (Grok-1.5, Grok-2)

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
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                        "content": {"type": "string"}
                    },
                    "required": ["role", "content"]
                }
            },
            "parameters": {
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "max_tokens": {"type": "integer", "minimum": 1},
                    "model": {"type": "string"},
                    "response_format": {"type": "object"},
                    "tools": {"type": "array"}
                }
            }
        },
        "required": ["messages"]
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
            },
            "tool_calls": {"type": "array"}
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
    async def generate_completion(self, messages: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a completion from the LLM based on the messages and parameters.
        Returns a dict with response, model_used, and usage information.
        """
        pass
    
    async def resolve(self, task: Task) -> Task:
        """
        Resolve the task by calling the LLM.
        """
        task.status = TaskStatus.IN_PROGRESS
        
        try:
            messages = task.input_data["messages"]
            parameters = task.input_data.get("parameters", {})
            
            result = await self.generate_completion(messages, parameters)
            
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
    TaskResolver for OpenAI models.
    """
    name = "OpenAIResolver"
    description = "Resolver for OpenAI GPT models"
    version = "1.0.0"
    
    def __init__(self, api_key: str = None, organization: str = None):
        """
        Initialize the OpenAI client.
        If api_key is not provided, it will be loaded from environment variables.
        """
        from openai import OpenAI
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided and not found in environment variables")
            
        client_args = {"api_key": self.api_key}
        if organization:
            client_args["organization"] = organization
            
        self.client = OpenAI(**client_args)
    
    async def generate_completion(self, messages: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate completions using OpenAI models.
        """
        model = parameters.get("model", "gpt-4o")
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        response_format = parameters.get("response_format")
        tools = parameters.get("tools")
        
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if response_format:
            kwargs["response_format"] = response_format
            
        if tools:
            kwargs["tools"] = tools
            
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                **kwargs
            )
            
            result = {
                "response": response.choices[0].message.content,
                "model_used": model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
            # Include tool calls if present
            if hasattr(response.choices[0].message, "tool_calls") and response.choices[0].message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }
                    for tool_call in response.choices[0].message.tool_calls
                ]
                
            return result
            
        except Exception as e:
            raise TaskError(
                code="openai_error",
                message=f"Error generating completion with OpenAI: {str(e)}",
                details={"provider": "OpenAI"}
            )
    
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
    
    async def generate_completion(self, messages: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate completions using Anthropic Claude models.
        """
        model = parameters.get("model", "claude-3-opus-20240229")
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        system = None
        
        # Extract system message if present
        anthropic_messages = []
        for message in messages:
            if message["role"] == "system":
                system = message["content"]
            else:
                anthropic_messages.append(message)
        
        kwargs = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if system:
            kwargs["system"] = system
            
        # Add tools if provided
        if "tools" in parameters:
            kwargs["tools"] = parameters["tools"]
            
        response = await asyncio.to_thread(
            self.client.messages.create,
            **kwargs
        )
        
        result = {
            "response": response.content[0].text,
            "model_used": model,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }
        
        # Include tool calls if present
        if hasattr(response, "tool_use") and response.tool_use:
            result["tool_calls"] = [
                {
                    "id": tool_use.id,
                    "name": tool_use.name,
                    "input": tool_use.input
                }
                for tool_use in response.tool_use
            ]
            
        return result
    
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
        self.api_key = api_key or os.getenv("TOGETHER_API_KEY")
        if not self.api_key:
            raise ValueError("Together AI API key not provided and not found in environment variables")
            
        self.api_url = api_url or os.getenv("TOGETHER_API_URL", "https://api.together.xyz/v1")
        self.timeout = timeout or int(os.getenv("TOGETHER_API_TIMEOUT", "120"))
        
        # Use httpx for async operations
        import httpx
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def generate_completion(self, messages: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate completions using Together AI models.
        """
        model = parameters.get("model", "meta-llama/Llama-3-70b-chat")
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # Add tools if provided
        if "tools" in parameters:
            payload["tools"] = parameters["tools"]
        
        # Add response format if provided
        if "response_format" in parameters:
            payload["response_format"] = parameters["response_format"]
        
        response = await self.client.post(
            f"{self.api_url}/chat/completions",
            json=payload
        )
        response.raise_for_status()
        response_data = response.json()
        
        result = {
            "response": response_data["choices"][0]["message"]["content"],
            "model_used": model,
            "usage": {
                "prompt_tokens": response_data["usage"]["prompt_tokens"],
                "completion_tokens": response_data["usage"]["completion_tokens"],
                "total_tokens": response_data["usage"]["total_tokens"]
            }
        }
        
        # Include tool calls if present
        if "tool_calls" in response_data["choices"][0]["message"]:
            result["tool_calls"] = response_data["choices"][0]["message"]["tool_calls"]
            
        return result
    
    async def health_check(self) -> bool:
        """
        Check if the Together AI API is accessible.
        """
        try:
            payload = {
                "model": "meta-llama/Llama-3-8b-chat",
                "messages": [{"role": "user", "content": "Hello, are you operational?"}],
                "max_tokens": 5
            }
            
            response = await self.client.post(
                f"{self.api_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"] is not None
        except Exception:
            return False
            
    async def close(self):
        """
        Close the HTTP client when done.
        """
        await self.client.aclose()
```

## xAI Resolver

```python
class XAIResolver(BaseLLMTaskResolver):
    """
    TaskResolver for xAI's Grok models.
    """
    name = "XAIResolver"
    description = "Task resolver for xAI's Grok models"
    version = "1.0.0"
    depth = 1
    evolution_strategy = "Evolve by improving prompts or switching to newer Grok models"
    
    def __init__(self, api_key: str = None, model: str = "grok-2"):
        """
        Initialize the xAI client.
        If api_key is not provided, it will be loaded from environment variables.
        """
        self.api_key = api_key or os.environ.get("XAI_API_KEY")
        self.model = model
        self.client = None
        
    def setup(self):
        """
        Initialize the xAI client.
        """
        if not self.api_key:
            raise ValueError("xAI API key is required")
        
        # Using httpx for async operations
        import httpx
        self.client = httpx.AsyncClient(
            base_url="https://api.groq.com/v1",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        
    async def generate_completion(self, messages: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate completions using xAI's Grok models.
        """
        if not self.client:
            self.setup()
            
        model = parameters.get("model", self.model)
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # Add tools if provided
        if "tools" in parameters:
            payload["tools"] = parameters["tools"]
        
        try:
            response = await self.client.post(
                "/chat/completions",
                json=payload
            )
            response.raise_for_status()
            response_data = response.json()
            
            # Format response data
            result = {
                "response": response_data["choices"][0]["message"]["content"],
                "model_used": model,
                "usage": {
                    "prompt_tokens": response_data["usage"]["prompt_tokens"],
                    "completion_tokens": response_data["usage"]["completion_tokens"],
                    "total_tokens": response_data["usage"]["total_tokens"]
                }
            }
            
            # Include tool calls if present
            if "tool_calls" in response_data["choices"][0]["message"]:
                result["tool_calls"] = response_data["choices"][0]["message"]["tool_calls"]
                
            return result
            
        except Exception as e:
            raise TaskError(
                code="xai_error",
                message=f"Error generating completion with xAI: {str(e)}",
                details={"provider": "xAI"}
            )
            
    async def health_check(self) -> bool:
        """
        Check if the xAI client is properly configured.
        """
        try:
            if not self.api_key:
                return False
                
            if not self.client:
                self.setup()
                
            # Simple test call to verify connectivity
            response = await self.client.get("/models")
            response.raise_for_status()
            return True
            
        except Exception:
            return False
            
    async def close(self):
        """
        Close the HTTP client when done.
        """
        if self.client:
            await self.client.aclose()
```

## Factory Pattern for LLM TaskResolvers

To simplify the creation and use of LLM TaskResolvers, we use a factory pattern:

```python
class LLMTaskResolverFactory:
    """
    Factory for creating LLM TaskResolvers.
    """
    
    @staticmethod
    async def create_resolver(provider: str, **kwargs) -> BaseLLMTaskResolver:
        """
        Create an LLM TaskResolver for the specified provider.
        
        Args:
            provider: The LLM provider ("openai", "anthropic", "together", "xai")
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
        elif provider == "xai":
            return XAIResolver(**kwargs)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    
    @staticmethod
    async def close_all_resolvers(resolvers: List[BaseLLMTaskResolver]):
        """
        Close all resolvers that have a close method.
        """
        for resolver in resolvers:
            if hasattr(resolver, "close") and callable(resolver.close):
                await resolver.close()
```

## Key Updates in LLM API Usage

1. **Exclusive ChatML Message Format**: All providers now require the ChatML format with role-based messages. Legacy single-prompt format is no longer supported.
2. **Tool/Function Calling**: All major providers now support tool/function calling with slightly different interfaces.
3. **Async HTTP Clients**: Using httpx for better async support in API calls.
4. **Resource Management**: Added proper client closing methods for long-running applications.
5. **Error Handling**: Improved error handling and reporting.
6. **New Models**: Updated to reference the latest models from each provider.

## Implementation Considerations

1. **Rate Limiting**: Implement retry logic with exponential backoff for rate limits.
2. **Streaming**: Add support for streaming responses where applicable.
3. **Caching**: Consider implementing response caching for identical prompts.
4. **Model Selection**: Implement automatic model fallback for when preferred models are unavailable.
5. **Cost Optimization**: Track token usage and implement budget controls 