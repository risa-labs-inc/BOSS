"""
Example script demonstrating the TaskResolverEvolver functionality.

This script creates a simple task resolver that randomly fails, records
the failures, and then evolves the resolver to improve its performance.
"""

import asyncio
import random
import logging
import sys
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set, Tuple, cast

try:
    from pydantic import BaseModel
    USING_PYDANTIC_V1 = hasattr(BaseModel, 'parse_obj')
    USING_PYDANTIC_V2 = hasattr(BaseModel, 'model_validate')
    print(f"Detected Pydantic version: {'v1' if USING_PYDANTIC_V1 else 'v2' if USING_PYDANTIC_V2 else 'unknown'}")
except ImportError:
    print("Error: Pydantic not installed. Please install it with 'poetry add pydantic'")
    sys.exit(1)

try:
    from boss.core.task_models import Task, TaskResult
    from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
    from boss.core.task_status import TaskStatus
    from boss.core.registry import TaskResolverRegistry, RegistryEntry
    from boss.core.evolver import (
        TaskResolverEvolver,
        EvolutionStrategy,
        SimplePromptEvolutionStrategy,
        EvolutionRecord
    )
except ImportError as e:
    print(f"Error importing BOSS modules: {e}")
    print("Make sure you're in the BOSS project directory and have installed dependencies.")
    print("Try: 'poetry install'")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Helper function for Pydantic compatibility
def get_model_dict(model):
    """Get model as dict, compatible with Pydantic v1 and v2."""
    try:
        # Try Pydantic v2 approach first
        return model.model_dump()
    except AttributeError:
        # Fall back to Pydantic v1 approach
        return model.dict()


class RandomFailResolver(TaskResolver):
    """A resolver that randomly fails some percentage of tasks."""
    
    def __init__(
        self, 
        metadata: TaskResolverMetadata, 
        failure_rate: float = 0.5
    ) -> None:
        """
        Initialize a new RandomFailResolver.
        
        Args:
            metadata: Metadata about this resolver.
            failure_rate: The percentage of tasks that should fail (0.0 to 1.0).
        """
        super().__init__(metadata)
        self.failure_rate = failure_rate
    
    async def health_check(self) -> bool:
        """Check if this resolver is healthy."""
        return True
    
    async def resolve(self, task: Task) -> TaskResult:
        """
        Resolve a task, randomly failing based on the failure rate.
        
        Args:
            task: The task to resolve.
            
        Returns:
            The result of the task.
        """
        # Random failure based on failure_rate
        if random.random() < self.failure_rate:
            logger.info(f"[{self.metadata.name} v{self.metadata.version}] Task {task.id} failed")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message="Random failure"
            )
        else:
            logger.info(f"[{self.metadata.name} v{self.metadata.version}] Task {task.id} succeeded")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={"result": f"Processed by {self.metadata.name} v{self.metadata.version}"}
            )


class ImprovedFailRateStrategy(EvolutionStrategy):
    """
    Evolution strategy that improves resolvers by reducing their failure rate.
    """
    
    def __init__(self, improvement_factor: float = 0.5) -> None:
        """
        Initialize a new ImprovedFailRateStrategy.
        
        Args:
            improvement_factor: The factor by which to reduce the failure rate.
                For example, 0.5 means the new failure rate will be half the old one.
        """
        super().__init__(
            name="ImprovedFailRateStrategy",
            description="Improves resolvers by reducing their failure rate"
        )
        self.improvement_factor = improvement_factor
    
    async def evolve(
        self, 
        resolver: TaskResolver,
        failed_tasks: List
    ) -> Optional[TaskResolver]:
        """
        Evolve a RandomFailResolver by reducing its failure rate.
        
        Args:
            resolver: The resolver to evolve.
            failed_tasks: The tasks that failed (not used in this strategy).
            
        Returns:
            An evolved resolver with a lower failure rate, or None if the
            resolver is not a RandomFailResolver.
        """
        if not isinstance(resolver, RandomFailResolver):
            logger.warning("Cannot evolve: resolver is not a RandomFailResolver")
            return None
        
        # Create a new resolver with a lower failure rate
        new_failure_rate = resolver.failure_rate * self.improvement_factor
        
        # Cap the minimum failure rate
        if new_failure_rate < 0.01:
            new_failure_rate = 0.01
        
        logger.info(f"Evolving resolver: failure rate {resolver.failure_rate:.2f} -> {new_failure_rate:.2f}")
        
        # Create new metadata
        new_metadata = TaskResolverMetadata(
            name=resolver.metadata.name,
            version=resolver.metadata.version,  # Version will be updated by the evolver
            description=f"{resolver.metadata.description} (evolved)",
            depth=resolver.metadata.depth,
            tags=resolver.metadata.tags.copy(),
            last_evolved=datetime.now()
        )
        
        # Create a new resolver with the updated failure rate
        evolved_resolver = RandomFailResolver(
            metadata=new_metadata,
            failure_rate=new_failure_rate
        )
        
        return evolved_resolver


async def run_task_batch(
    resolver: TaskResolver, 
    count: int
) -> List[Tuple[Task, TaskResult]]:
    """
    Run a batch of tasks and collect the results.
    
    Args:
        resolver: The resolver to use.
        count: The number of tasks to run.
        
    Returns:
        A list of (task, result) tuples.
    """
    results = []
    for i in range(count):
        task = Task(
            name=f"test_task_{i}",
            input_data={"test_value": i}
        )
        result = await resolver.resolve(task)
        results.append((task, result))
    return results


async def main():
    """Main function to demonstrate the TaskResolverEvolver."""
    try:
        print("Starting TaskResolverEvolver demonstration...")
        
        # Create a registry
        registry = TaskResolverRegistry()
        print("Created registry")
        
        # Create a simple resolver that fails 80% of the time
        initial_resolver = RandomFailResolver(
            metadata=TaskResolverMetadata(
                name="RandomResolver",
                version="1.0.0",
                description="A resolver that randomly fails",
                depth=1,
                tags=["test", "random"]
            ),
            failure_rate=0.8
        )
        print("Created initial resolver with 80% failure rate")
        
        # Register the resolver
        registry.register(initial_resolver)
        print("Registered resolver with registry")
        
        # Create an evolver with our custom strategy
        evolver = TaskResolverEvolver(
            metadata=TaskResolverMetadata(
                name="TaskResolverEvolver",
                version="1.0.0",
                description="Evolves task resolvers based on performance"
            ),
            registry=registry,
            strategies=[ImprovedFailRateStrategy()],
            failure_threshold=5,  # Evolve after 5 failures
            min_time_between_evolutions=timedelta(seconds=0)  # No waiting time between evolutions
        )
        print("Created evolver with ImprovedFailRateStrategy")
        
        print("\n=== Initial Resolver ===")
        print(f"Name: {initial_resolver.metadata.name}")
        print(f"Version: {initial_resolver.metadata.version}")
        print(f"Failure Rate: {initial_resolver.failure_rate:.2f}")
        
        # Run some tasks and collect results
        print("\nRunning initial tasks...")
        initial_results = await run_task_batch(initial_resolver, 10)
        success_count = sum(1 for _, result in initial_results if result.status == TaskStatus.COMPLETED)
        
        print(f"\nRan 10 tasks:")
        print(f"  Successes: {success_count}")
        print(f"  Failures: {10 - success_count}")
        
        # Record the failures with the evolver
        failed_results = [(task, result) for task, result in initial_results if result.status == TaskStatus.ERROR]
        
        print("\n=== Recording Failures with Evolver ===")
        for i, (task, result) in enumerate(failed_results):
            print(f"Recording failure {i+1}/{len(failed_results)}...")
            record_task = Task(
                name="record_failure",
                input_data={
                    "operation": "record_failure",
                    "resolver_name": "RandomResolver",
                    "failed_task": get_model_dict(task),
                    "failed_result": get_model_dict(result)
                }
            )
            record_result = await evolver.resolve(record_task)
            eligible = record_result.output_data.get("evolution_eligible", False)
            failures = record_result.output_data.get("failed_tasks_count", 0)
            print(f"Recorded failure: {failures} total failures, eligible for evolution: {eligible}")
        
        # Check if eligible for evolution
        print("\nChecking evolution eligibility...")
        check_task = Task(
            name="check_eligibility",
            input_data={
                "operation": "check_evolution_eligibility",
                "resolver_name": "RandomResolver"
            }
        )
        check_result = await evolver.resolve(check_task)
        
        print("\n=== Evolution Eligibility ===")
        print(f"Eligible: {check_result.output_data.get('eligible', False)}")
        print(f"Reason: {check_result.output_data.get('reason', 'Unknown')}")
        
        # Evolve the resolver
        print("\nEvolving resolver...")
        evolve_task = Task(
            name="evolve_resolver",
            input_data={
                "operation": "evolve_resolver",
                "resolver_name": "RandomResolver",
                "force": check_result.output_data.get('eligible', False) == False  # Force evolution if not eligible
            }
        )
        evolve_result = await evolver.resolve(evolve_task)
        
        print("\n=== Evolution Result ===")
        if evolve_result.output_data.get("evolved", False):
            print("Evolution successful!")
            print(f"Original: {evolve_result.output_data['original_resolver']['name']} " +
                 f"v{evolve_result.output_data['original_resolver']['version']}")
            print(f"Evolved: {evolve_result.output_data['evolved_resolver']['name']} " +
                 f"v{evolve_result.output_data['evolved_resolver']['version']}")
            
            # Get the evolved resolver
            evolved_name = evolve_result.output_data["evolved_resolver"]["name"]
            evolved_version = evolve_result.output_data["evolved_resolver"]["version"]
            evolved_resolver = registry.get_resolver(evolved_name, evolved_version)
            
            if evolved_resolver and isinstance(evolved_resolver, RandomFailResolver):
                print(f"New Failure Rate: {evolved_resolver.failure_rate:.2f}")
                
                # Test the evolved resolver
                print("\n=== Testing Evolved Resolver ===")
                evolved_results = await run_task_batch(evolved_resolver, 10)
                evolved_success_count = sum(1 for _, result in evolved_results 
                                          if result.status == TaskStatus.COMPLETED)
                
                print(f"Ran 10 tasks:")
                print(f"  Successes: {evolved_success_count}")
                print(f"  Failures: {10 - evolved_success_count}")
                
                # Compare
                print("\n=== Performance Comparison ===")
                print(f"Original Success Rate: {success_count/10:.1%}")
                print(f"Evolved Success Rate: {evolved_success_count/10:.1%}")
                
                if evolved_success_count > success_count:
                    print("Evolution improved performance!")
                else:
                    print("Evolution did not improve performance.")
        else:
            print("Evolution failed.")
            print(f"Reason: {evolve_result.output_data.get('reason', 'Unknown')}")
        
        # Get the evolution history
        print("\nGetting evolution history...")
        history_task = Task(
            name="get_history",
            input_data={
                "operation": "get_evolution_history"
            }
        )
        history_result = await evolver.resolve(history_task)
        
        print("\n=== Evolution History ===")
        if history_result.output_data["history"]:
            for record in history_result.output_data["history"]:
                print(f"{record['original_resolver_name']} v{record['original_resolver_version']} -> " +
                     f"{record['evolved_resolver_name']} v{record['evolved_resolver_version']}")
                print(f"Reason: {record['evolution_reason']}")
                print(f"Date: {record['evolution_date']}")
                print("")
        else:
            print("No evolution history found.")
            
        print("\nTaskResolverEvolver demonstration completed successfully!")
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 