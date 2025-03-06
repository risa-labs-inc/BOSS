# Lighthouse Design Document

## Overview

Lighthouse is the data management component of the BOSS system. It provides storage, registry, and API services for TaskResolvers, Masteries, and organizational context. Lighthouse uses GraphQL with vector plugins and caching to provide efficient access to the system's resources.

## Core Components

### 1. Registry System

The Registry System maintains catalogs of TaskResolvers and Masteries. It provides:

- Storage for TaskResolver and Mastery metadata
- Vector search for finding relevant TaskResolvers and Masteries
- Version tracking for evolution history
- Health status monitoring

#### TaskResolver Registry

```python
class TaskResolverRegistry:
    """
    Registry for TaskResolvers in the BOSS system.
    """
    
    async def register(self, resolver: TaskResolver) -> str:
        """
        Register a new TaskResolver in the registry.
        Returns the ID of the registered resolver.
        """
        pass
        
    async def get_resolver(self, resolver_id: str) -> TaskResolver:
        """
        Get a TaskResolver by its ID.
        """
        pass
        
    async def search(self, query: str, limit: int = 10) -> List[TaskResolver]:
        """
        Search for TaskResolvers by description or capabilities.
        Uses vector search for semantic matching.
        """
        pass
        
    async def health_check(self, resolver_id: str = None) -> Dict[str, bool]:
        """
        Check the health of one or all TaskResolvers.
        Returns a mapping of resolver IDs to health status.
        """
        pass
        
    async def get_version_history(self, resolver_id: str) -> List[Dict[str, Any]]:
        """
        Get the version history of a TaskResolver.
        """
        pass
        
    async def update(self, resolver_id: str, resolver: TaskResolver) -> str:
        """
        Update an existing TaskResolver.
        Returns the ID of the updated resolver.
        """
        pass
```

#### Mastery Registry

```python
class MasteryRegistry:
    """
    Registry for Masteries in the BOSS system.
    """
    
    async def register(self, mastery: Mastery) -> str:
        """
        Register a new Mastery in the registry.
        Returns the ID of the registered mastery.
        """
        pass
        
    async def get_mastery(self, mastery_id: str) -> Mastery:
        """
        Get a Mastery by its ID.
        """
        pass
        
    async def search(self, query: str, limit: int = 10) -> List[Mastery]:
        """
        Search for Masteries by description or capabilities.
        Uses vector search for semantic matching.
        """
        pass
        
    async def get_version_history(self, mastery_id: str) -> List[Dict[str, Any]]:
        """
        Get the version history of a Mastery.
        """
        pass
        
    async def update(self, mastery_id: str, mastery: Mastery) -> str:
        """
        Update an existing Mastery.
        Returns the ID of the updated mastery.
        """
        pass
```

### 2. Database System

The Database System provides storage for:

- TaskResolver and Mastery metadata and code
- Worklist items (tasks to be performed)
- Organizational context and values
- Execution history and metrics
- User accounts and access control

Database models:

```python
class TaskResolverModel(BaseModel):
    id: str
    name: str
    description: str
    version: str
    depth: int
    evolution_strategy: str
    input_schema: Dict[str, Any]
    result_schema: Dict[str, Any]
    error_schema: Dict[str, Any]
    code: str
    created_at: datetime
    updated_at: datetime
    vector_embedding: Optional[List[float]] = None
    health_status: bool = True
    metadata: Dict[str, Any] = {}

class MasteryModel(BaseModel):
    id: str
    name: str
    description: str
    version: str
    input_schema: Dict[str, Any]
    result_schema: Dict[str, Any]
    error_schema: Dict[str, Any]
    code: str
    created_at: datetime
    updated_at: datetime
    vector_embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = {}

class WorklistItemModel(BaseModel):
    id: str
    description: str
    input_data: Dict[str, Any]
    status: TaskStatus
    priority: int
    created_at: datetime
    updated_at: datetime
    deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}

class OrganizationContextModel(BaseModel):
    id: str
    name: str
    description: str
    values: Dict[str, Any]
    goals: List[Dict[str, Any]]
    kpis: List[Dict[str, Any]]
    structure: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}

class ExecutionHistoryModel(BaseModel):
    id: str
    task_id: str
    mastery_id: Optional[str]
    resolvers_used: List[str]
    start_time: datetime
    end_time: datetime
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
```

### 3. GraphQL API

The Lighthouse API provides a GraphQL interface for:

- Registering and retrieving TaskResolvers and Masteries
- Managing the worklist
- Accessing organizational context
- Viewing execution history
- User authentication and authorization

Example GraphQL Schema:

```graphql
type TaskResolver {
  id: ID!
  name: String!
  description: String!
  version: String!
  depth: Int!
  evolutionStrategy: String!
  inputSchema: JSONObject!
  resultSchema: JSONObject!
  errorSchema: JSONObject!
  createdAt: DateTime!
  updatedAt: DateTime!
  healthStatus: Boolean!
  metadata: JSONObject
}

type Mastery {
  id: ID!
  name: String!
  description: String!
  version: String!
  inputSchema: JSONObject!
  resultSchema: JSONObject!
  errorSchema: JSONObject!
  createdAt: DateTime!
  updatedAt: DateTime!
  metadata: JSONObject
}

type WorklistItem {
  id: ID!
  description: String!
  inputData: JSONObject!
  status: TaskStatus!
  priority: Int!
  createdAt: DateTime!
  updatedAt: DateTime!
  deadline: DateTime
  assignedTo: String
  result: JSONObject
  error: JSONObject
  metadata: JSONObject
}

enum TaskStatus {
  PENDING
  IN_PROGRESS
  COMPLETED
  FAILED
}

type OrganizationContext {
  id: ID!
  name: String!
  description: String!
  values: JSONObject!
  goals: [JSONObject!]!
  kpis: [JSONObject!]!
  structure: JSONObject!
  createdAt: DateTime!
  updatedAt: DateTime!
  metadata: JSONObject
}

type Query {
  taskResolver(id: ID!): TaskResolver
  searchTaskResolvers(query: String!, limit: Int): [TaskResolver!]!
  mastery(id: ID!): Mastery
  searchMasteries(query: String!, limit: Int): [Mastery!]!
  worklistItem(id: ID!): WorklistItem
  worklistItems(status: TaskStatus, limit: Int, offset: Int): [WorklistItem!]!
  organizationContext(id: ID!): OrganizationContext
  healthCheck: Boolean!
}

type Mutation {
  registerTaskResolver(input: RegisterTaskResolverInput!): TaskResolver!
  updateTaskResolver(id: ID!, input: UpdateTaskResolverInput!): TaskResolver!
  registerMastery(input: RegisterMasteryInput!): Mastery!
  updateMastery(id: ID!, input: UpdateMasteryInput!): Mastery!
  createWorklistItem(input: CreateWorklistItemInput!): WorklistItem!
  updateWorklistItem(id: ID!, input: UpdateWorklistItemInput!): WorklistItem!
  executeTask(worklistItemId: ID!): TaskExecutionResult!
  updateOrganizationContext(id: ID!, input: UpdateOrganizationContextInput!): OrganizationContext!
}

input RegisterTaskResolverInput {
  name: String!
  description: String!
  version: String!
  depth: Int!
  evolutionStrategy: String!
  inputSchema: JSONObject!
  resultSchema: JSONObject!
  errorSchema: JSONObject!
  code: String!
  metadata: JSONObject
}

# Additional input types omitted for brevity

type TaskExecutionResult {
  status: TaskStatus!
  result: JSONObject
  error: JSONObject
  masteryId: ID
  executionTime: Float!
}

scalar JSONObject
scalar DateTime
```

### 4. Web Interface

The Lighthouse Web Interface provides a user-friendly way to:

- View and manage the worklist
- Monitor TaskResolver and Mastery health
- View execution history and metrics
- Configure organizational context
- Create new BOSS instances for other organizations

The web interface will be built using a modern frontend framework (e.g., React) and will communicate with the Lighthouse API.

### 5. Context Registry

The Context Registry maintains organizational context information:

- Goals and objectives
- KPIs and metrics
- Organizational structure
- Historical data
- Values and priorities

This context is used by Lanagers when composing and executing Masteries to ensure alignment with organizational objectives.

## Vector Search Implementation

Lighthouse uses vector embeddings to enable semantic search for TaskResolvers and Masteries:

1. **Embedding Generation**: When a TaskResolver or Mastery is registered, generate vector embeddings for its description, input/output schemas, and capabilities.

2. **Vector Storage**: Store these embeddings in a vector database (e.g., PostgreSQL with pgvector extension).

3. **Similarity Search**: When searching for TaskResolvers or Masteries, convert the search query to an embedding and find the most similar vectors in the database.

## Caching Strategy

Lighthouse implements a multi-level caching strategy:

1. **Registry Cache**: Cache frequently accessed TaskResolvers and Masteries in memory.

2. **Query Cache**: Cache the results of common GraphQL queries.

3. **Vector Cache**: Cache vector search results for common queries.

4. **Code Cache**: Cache compiled TaskResolver and Mastery code for faster execution.

## BOSS Replication

Lighthouse provides functionality to replicate the entire BOSS system for other organizations:

1. **Repository Creation**: Create a new Git repository for the organization.

2. **Core Component Copy**: Copy the core components (Lanager and Lighthouse) to the new repository.

3. **Configuration**: Set up environment variables and configurations for the new instance.

4. **Initialization**: Initialize the database and registries with default TaskResolvers and Masteries.

5. **Context Setup**: Set up organizational context for the new organization.

This functionality is protected by authentication and authorization controls in the web interface. 