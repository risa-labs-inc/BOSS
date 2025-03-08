"""
MasteryComposer module that implements the TaskResolver for composing masteries from other TaskResolvers.

This is a key component in the Lanager framework, allowing for the creation of sophisticated workflows
by chaining multiple TaskResolvers together in configurable patterns.
"""

import logging
from typing import Any, Dict, List, Optional, Union, Callable, Type, cast

from boss.core.task_base import Task, TaskMetadata
from boss.core.task_result import TaskResult
from boss.core.task_error import TaskError
from boss.core.task_status import TaskStatus
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_retry import TaskRetryManager


class MasteryNode:
    """Represents a node in a mastery composition graph."""
    
    def __init__(
        self, 
        resolver: TaskResolver, 
        id: str,
        next_nodes: Optional[List[str]] = None,
        condition: Optional[Callable[[TaskResult], bool]] = None
    ) -> None:
        """
        Initialize a mastery node.
        
        Args:
            resolver: The TaskResolver to execute at this node
            id: Unique identifier for this node
            next_nodes: List of node IDs to execute after this one
            condition: Optional condition function that determines if this node's output should 
                       be passed to the next nodes
        """
        self.resolver = resolver
        self.id = id
        self.next_nodes = next_nodes or []
        self.condition = condition
    
    def can_proceed(self, result: TaskResult) -> bool:
        """
        Determine if execution can proceed to the next nodes.
        
        Args:
            result: The TaskResult from this node's execution
            
        Returns:
            True if execution should proceed to next nodes, False otherwise
        """
        # If there's a condition function, use it
        if self.condition:
            return self.condition(result)
        
        # Default behavior: proceed if the task was successful
        return result.status == TaskStatus.COMPLETED


class MasteryComposer(TaskResolver):
    """
    TaskResolver that composes multiple TaskResolvers into a mastery workflow.
    
    This allows for complex task resolution patterns by chaining, branching,
    and conditionally executing different TaskResolvers.
    """
    
    def __init__(
        self,
        metadata: TaskResolverMetadata,
        nodes: Dict[str, MasteryNode],
        entry_node: str,
        exit_nodes: Optional[List[str]] = None,
        retry_manager: Optional[TaskRetryManager] = None,
        max_depth: int = 10,
    ) -> None:
        """
        Initialize the MasteryComposer.
        
        Args:
            metadata: Metadata for this resolver
            nodes: Dictionary mapping node IDs to MasteryNode instances
            entry_node: ID of the entry node where execution begins
            exit_nodes: List of exit node IDs where execution can end
            retry_manager: Optional TaskRetryManager for handling retries
            max_depth: Maximum depth of execution to prevent infinite loops
        """
        super().__init__(metadata)
        self.nodes = nodes
        self.entry_node = entry_node
        self.exit_nodes = exit_nodes or []
        self.max_depth = max_depth
        self.retry_manager = retry_manager
        self.logger = logging.getLogger(__name__)
        
        # Validate the configuration
        self._validate_configuration()
    
    async def resolve(self, task: Task) -> Union[TaskResult, Any]:
        """
        Resolve a task by executing the mastery composition.
        
        This is the main entry point required by the TaskResolver interface.
        It delegates to the _resolve_task method.
        
        Args:
            task: The task to resolve
            
        Returns:
            The final TaskResult
        """
        return await self._resolve_task(task)
    
    def _validate_configuration(self) -> None:
        """Validate the mastery configuration."""
        # Ensure entry node exists
        if self.entry_node not in self.nodes:
            raise ValueError(f"Entry node '{self.entry_node}' not found in nodes")
        
        # Ensure exit nodes exist
        for exit_node in self.exit_nodes:
            if exit_node not in self.nodes:
                raise ValueError(f"Exit node '{exit_node}' not found in nodes")
        
        # Ensure all next_node references are valid
        for node_id, node in self.nodes.items():
            for next_node in node.next_nodes:
                if next_node not in self.nodes:
                    raise ValueError(f"Node '{node_id}' references non-existent next node '{next_node}'")
    
    async def health_check(self) -> bool:
        """
        Check if the mastery composition is healthy.
        
        This checks the health of all resolvers in the composition.
        
        Returns:
            True if the composition is healthy, False otherwise
        """
        try:
            # Check the health of all resolvers
            for node_id, node in self.nodes.items():
                resolver_healthy = await node.resolver.health_check()
                if not resolver_healthy:
                    self.logger.error(f"Resolver for node '{node_id}' is unhealthy")
                    return False
            
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False
    
    async def _execute_node(self, node_id: str, task: Task, depth: int = 0) -> TaskResult:
        """
        Execute a single node in the mastery.
        
        Args:
            node_id: ID of the node to execute
            task: Task to execute
            depth: Current execution depth
            
        Returns:
            The TaskResult from the node execution
        """
        # Get the node
        node = self.nodes.get(node_id)
        if not node:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Node '{node_id}' not found"
            )
        
        # Execute the node's resolver
        try:
            result = await node.resolver(task)
            
            # Create a new result with the executed_node information
            output_data = result.output_data.copy() if hasattr(result, 'output_data') else {}
            output_data["executed_node"] = node_id
            
            return TaskResult(
                task_id=task.id,
                status=result.status,
                output_data=output_data,
                message=result.message if hasattr(result, 'message') else None
            )
        except Exception as e:
            self.logger.error(f"Error executing node '{node_id}': {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                message=f"Error executing node '{node_id}': {str(e)}"
            )
    
    async def _resolve_task(self, task: Task) -> TaskResult:
        """
        Resolve a task by executing the mastery composition.
        
        Args:
            task: The task to resolve
            
        Returns:
            The final TaskResult
        """
        depth = 0
        current_node_id = self.entry_node
        current_task = task
        execution_path = [current_node_id]
        
        # Execute nodes until we reach an exit node or run out of nodes to execute
        while depth < self.max_depth:
            # Execute the current node
            result = await self._execute_node(current_node_id, current_task, depth)
            
            # Update the task for the next node
            current_task = Task(
                id=task.id,
                name=task.name,
                description=task.description,
                input_data=result.output_data,
                metadata=TaskMetadata()  # Create a new empty metadata
            )
            
            # If we've reached an exit node, return the result
            if current_node_id in self.exit_nodes:
                self.logger.info(f"Reached exit node {current_node_id}. Execution path: {' -> '.join(execution_path)}")
                return result
            
            # Check if we can proceed to the next nodes
            node = self.nodes[current_node_id]
            if not node.can_proceed(result):
                self.logger.info(f"Node {current_node_id} condition not met, stopping execution")
                return result
            
            # If there are no next nodes, we're done
            if not node.next_nodes:
                self.logger.info(f"Node {current_node_id} has no next nodes, stopping execution")
                return result
            
            # Move to the next node
            current_node_id = node.next_nodes[0]  # Simple implementation: just take the first next node
            execution_path.append(current_node_id)
            depth += 1
        
        # If we get here, we've exceeded the maximum depth
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.ERROR,
            message=f"Maximum execution depth ({self.max_depth}) exceeded"
        )
    
    def can_handle(self, task: Task) -> bool:
        """
        Determine if this resolver can handle the given task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this resolver can handle the task, False otherwise
        """
        # Check if the task specifically requests this resolver
        resolver_name = task.input_data.get("resolver", "") if task.input_data else ""
        return bool(resolver_name == self.metadata.name or resolver_name == "")
    
    @classmethod
    def create_linear_mastery(
        cls,
        metadata: TaskResolverMetadata,
        resolvers: List[TaskResolver],
        retry_manager: Optional[TaskRetryManager] = None
    ) -> "MasteryComposer":
        """
        Create a linear mastery where resolvers are executed in sequence.
        
        Args:
            metadata: Metadata for the mastery
            resolvers: List of resolvers to execute in sequence
            retry_manager: Optional TaskRetryManager for handling retries
            
        Returns:
            A MasteryComposer configured as a linear mastery
        """
        if not resolvers:
            raise ValueError("At least one resolver is required")
        
        nodes = {}
        for i, resolver in enumerate(resolvers):
            node_id = resolver.metadata.name
            next_node = [resolvers[i+1].metadata.name] if i < len(resolvers) - 1 else []
            nodes[node_id] = MasteryNode(resolver, node_id, next_node)
        
        return cls(
            metadata=metadata,
            nodes=nodes,
            entry_node=resolvers[0].metadata.name,
            exit_nodes=[resolvers[-1].metadata.name],
            retry_manager=retry_manager
        )
    
    @classmethod
    def create_conditional_mastery(
        cls,
        metadata: TaskResolverMetadata,
        decision_resolver: TaskResolver,
        condition_map: Dict[Any, TaskResolver],
        default_resolver: Optional[TaskResolver] = None,
        retry_manager: Optional[TaskRetryManager] = None
    ) -> "MasteryComposer":
        """
        Create a conditional mastery where the path depends on the output of a decision resolver.
        
        Args:
            metadata: Metadata for the mastery
            decision_resolver: Resolver that decides which path to take
            condition_map: Mapping from decision outputs to resolvers
            default_resolver: Optional default resolver if no condition matches
            retry_manager: Optional TaskRetryManager for handling retries
            
        Returns:
            A MasteryComposer configured as a conditional mastery
        """
        nodes = {}
        
        # Decision node
        decision_node_id = "decision"
        nodes[decision_node_id] = MasteryNode(
            resolver=decision_resolver,
            id=decision_node_id,
            next_nodes=["output"]
        )
        
        # Create a complex condition function
        def route_condition(result: TaskResult) -> bool:
            decision_key = "decision"
            if decision_key in result.output_data:
                decision_value = result.output_data[decision_key]
                return decision_value in condition_map
            return False
        
        # Output node with different resolvers based on the decision
        def get_resolver_for_output(task: Task) -> TaskResolver:
            # Extract the decision value from the input data
            decision_key = "decision"
            decision_value = None
            
            # Look for the decision directly in the input data
            if task.input_data and isinstance(task.input_data, dict):
                if decision_key in task.input_data:
                    decision_value = task.input_data[decision_key]
            
            # If we couldn't find a decision, use the default
            if decision_value is None or decision_value not in condition_map:
                return default_resolver or list(condition_map.values())[0]
            
            return condition_map[decision_value]
        
        class DynamicResolver(TaskResolver):
            def __init__(self, metadata: TaskResolverMetadata) -> None:
                super().__init__(metadata)
            
            async def resolve(self, task: Task) -> TaskResult:
                """Implement the required abstract resolve method."""
                resolver = get_resolver_for_output(task)
                return await resolver(task)
            
            def _resolve_task(self, task: Task) -> TaskResult:
                resolver = get_resolver_for_output(task)
                return resolver(task)
        
        output_node_id = "output"
        nodes[output_node_id] = MasteryNode(
            resolver=DynamicResolver(TaskResolverMetadata(
                name="dynamic_resolver",
                version="1.0.0",
                description="Dynamically selects a resolver based on input"
            )),
            id=output_node_id,
            next_nodes=[]
        )
        
        return cls(
            metadata=metadata,
            nodes=nodes,
            entry_node=decision_node_id,
            exit_nodes=[output_node_id],
            retry_manager=retry_manager
        ) 