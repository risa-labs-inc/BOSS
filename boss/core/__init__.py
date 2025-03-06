"""
Core components of the BOSS system.

This package contains the core components of the BOSS system, including
task models, task resolvers, and related utilities.
"""

from boss.core.task_models import Task, TaskResult, TaskError, TaskMetadata
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus
from boss.core.task_retry import TaskRetryManager, BackoffStrategy
from boss.core.base_llm_resolver import BaseLLMTaskResolver, LLMResponse
from boss.core.llm_factory import LLMTaskResolverFactory
from boss.core.mastery_composer import MasteryComposer, MasteryNode
from boss.core.mastery_registry import MasteryRegistry, MasteryDefinition
from boss.core.mastery_executor import MasteryExecutor, ExecutionState
from boss.core.registry import TaskResolverRegistry, RegistryEntry
from boss.core.health_check_resolver import HealthCheckResolver, HealthCheckResult
from boss.core.vector_search_resolver import VectorSearchResolver, VectorSearchResult

# Import LLM resolvers
from boss.core.openai_resolver import OpenAITaskResolver
from boss.core.anthropic_resolver import AnthropicTaskResolver

# Try to import optional resolvers
try:
    from boss.core.together_ai_resolver import TogetherAITaskResolver
    HAS_TOGETHER_AI = True
except ImportError:
    HAS_TOGETHER_AI = False

try:
    from boss.core.xai_resolver import XAITaskResolver
    HAS_XAI = True
except ImportError:
    HAS_XAI = False

__all__ = [
    # Task models
    "Task",
    "TaskResult",
    "TaskError",
    "TaskMetadata",
    
    # Task resolver
    "TaskResolver",
    "TaskResolverMetadata",
    
    # Task status
    "TaskStatus",
    
    # Task retry
    "TaskRetryManager",
    "BackoffStrategy",
    
    # LLM resolvers
    "BaseLLMTaskResolver",
    "LLMResponse",
    "LLMTaskResolverFactory",
    "OpenAITaskResolver",
    "AnthropicTaskResolver",
    
    # Mastery components
    "MasteryComposer",
    "MasteryNode",
    "MasteryRegistry",
    "MasteryDefinition",
    "MasteryExecutor",
    "ExecutionState",
    
    # Registry components
    "TaskResolverRegistry",
    "RegistryEntry",
    
    # Health check components
    "HealthCheckResolver",
    "HealthCheckResult",
    
    # Vector search components
    "VectorSearchResolver",
    "VectorSearchResult",
]

# Add optional resolvers to __all__ if available
if HAS_TOGETHER_AI:
    __all__.append("TogetherAITaskResolver")

if HAS_XAI:
    __all__.append("XAITaskResolver")
