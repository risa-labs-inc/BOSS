"""
Example demonstrating the use of TaskPrioritizationResolver.

This example shows how to create and use the TaskPrioritizationResolver to assign
priority scores to tasks based on various factors.
"""

import asyncio
from datetime import datetime, timedelta

from boss.core.task_models import Task, TaskStatus
from boss.core.task_resolver import TaskResolverMetadata
from boss.utility.task_prioritization_resolver import TaskPrioritizationResolver, PriorityFactor


async def main():
    """Run the task prioritization example."""
    print("=== Task Prioritization Resolver Example ===")
    
    # Create metadata for the resolver
    metadata = TaskResolverMetadata(
        name="ExampleTaskPrioritization",
        version="1.0.0",
        description="Example task prioritization for demonstration"
    )
    
    # Create the task prioritization resolver
    prioritizer = TaskPrioritizationResolver(
        metadata=metadata,
        priority_scale=10  # Use a 0-10 scale
    )
    
    # Check if the resolver is healthy
    is_healthy = await prioritizer.health_check()
    print(f"Resolver health check: {'Healthy' if is_healthy else 'Unhealthy'}")
    
    # Example 1: Create a basic task with no special properties
    print("\n=== Example 1: Basic task with no special properties ===")
    basic_task = Task(
        name="basic_task",
        description="A basic task with no special properties",
        metadata={}
    )
    
    # Calculate priority directly
    basic_priority = prioritizer.calculate_priority(basic_task)
    print(f"Basic task priority: {basic_priority:.2f}/10")
    
    # Example 2: Create tasks with different properties to show priority differences
    print("\n=== Example 2: Tasks with different properties ===")
    
    # Task with high explicit priority
    high_priority_task = Task(
        name="high_priority_task",
        description="Task with high explicit priority",
        metadata={"priority": 8}
    )
    
    # Task with a deadline
    deadline_task = Task(
        name="deadline_task",
        description="Task with upcoming deadline",
        metadata={"deadline": datetime.now() + timedelta(hours=12)}
    )
    
    # Old task
    old_task = Task(
        name="old_task",
        description="Task created a while ago",
        metadata={"created_at": datetime.now() - timedelta(hours=20)}
    )
    
    # VIP user task
    vip_task = Task(
        name="vip_task",
        description="Task from a VIP user",
        metadata={"owner": "vip_user1"}
    )
    
    # Task with many dependencies
    dependency_task = Task(
        name="dependency_task",
        description="Task with many dependencies",
        context={"dependencies": ["task1", "task2", "task3", "task4", "task5"]}
    )
    
    # Calculate priorities with a context that includes VIP users
    context = {"vip_users": {"vip_user1", "vip_user2"}, "high_priority_users": {"user3", "user4"}}
    
    tasks = [high_priority_task, deadline_task, old_task, vip_task, dependency_task]
    for task in tasks:
        priority = prioritizer.calculate_priority(task, context)
        print(f"{task.name}: {priority:.2f}/10")
    
    # Example 3: Get detailed priority breakdown
    print("\n=== Example 3: Detailed priority breakdown ===")
    details = prioritizer.get_priority_details(deadline_task, context)
    
    print(f"Task: {details['task_name']}")
    print(f"Final priority score: {details['final_priority_score']:.2f}/{details['priority_scale']}")
    print("Factor breakdown:")
    
    for factor in details["factor_breakdown"]:
        print(f"  - {factor['name']}: {factor['weighted_score']:.2f} ({factor['percentage_of_total']})")
        print(f"    {factor['description']}")
    
    # Example 4: Prioritize tasks using the resolver API
    print("\n=== Example 4: Prioritize tasks using resolver API ===")
    
    # Create a task to prioritize multiple tasks
    prioritize_task = Task(
        name="prioritize_tasks",
        description="Prioritize multiple tasks",
        input_data={
            "tasks": [high_priority_task, deadline_task, old_task, vip_task, dependency_task],
            "context": context
        }
    )
    
    # Check if the resolver can handle this task
    can_handle = prioritizer.can_handle(prioritize_task)
    print(f"Can handle task: {can_handle}")
    
    if can_handle:
        # Resolve the task
        result = await prioritizer._resolve_task(prioritize_task)
        
        # Print the result
        print(f"Task status: {result.status}")
        if result.status == TaskStatus.COMPLETED:
            print("Prioritized tasks (highest to lowest):")
            for i, task_result in enumerate(result.output_data["prioritized_tasks"]):
                print(f"{i+1}. Task ID: {task_result['task_id']}, Priority: {task_result['priority']:.2f}")
    
    # Example 5: Add a custom priority factor
    print("\n=== Example 5: Adding a custom priority factor ===")
    
    # Define a custom priority factor for tasks with "urgent" in the name
    def evaluate_urgent_name(task: Task, context: dict) -> float:
        """Return 1.0 if the task name contains 'urgent', 0.0 otherwise."""
        if "urgent" in task.name.lower():
            return 1.0
        return 0.0
    
    urgent_factor = PriorityFactor(
        name="urgent_name",
        weight=0.3,
        evaluation_fn=evaluate_urgent_name,
        description="Priority based on 'urgent' in the task name"
    )
    
    # Add the factor to the resolver
    prioritizer.add_priority_factor(urgent_factor)
    
    # Create a task with "urgent" in the name
    urgent_task = Task(
        name="urgent_data_backup",
        description="Urgent task that needs immediate attention",
        metadata={}
    )
    
    # Get priority before and after adding the factor
    before_priority = prioritizer.calculate_priority(basic_task)
    urgent_priority = prioritizer.calculate_priority(urgent_task)
    
    print(f"Basic task (no 'urgent' in name): {before_priority:.2f}/10")
    print(f"Urgent task (with 'urgent' in name): {urgent_priority:.2f}/10")
    
    # Get detailed breakdown
    urgent_details = prioritizer.get_priority_details(urgent_task)
    print("\nUrgent task factor breakdown:")
    for factor in urgent_details["factor_breakdown"]:
        if factor["weighted_score"] > 0:
            print(f"  - {factor['name']}: {factor['weighted_score']:.2f} ({factor['percentage_of_total']})")


if __name__ == "__main__":
    asyncio.run(main()) 