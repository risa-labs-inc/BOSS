"""Tests for the OrganizationSetupResolver."""

import json
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, cast
import unittest
from unittest.mock import MagicMock, patch

from boss.core.task_models import Task, TaskMetadata, TaskResult  # type: ignore[import]
from boss.core.task_resolver import TaskResolverMetadata  # type: ignore[import]
from boss.core.task_status import TaskStatus  # type: ignore[import]
from boss.utility.organization_setup_resolver import OrganizationSetupResolver  # type: ignore[import]


class TestOrganizationSetupResolver(unittest.IsolatedAsyncioTestCase):
    """Test suite for the OrganizationSetupResolver."""

    def setUp(self) -> None:
        """Set up the test environment."""
        # Create temp directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.boss_home_dir = os.path.join(self.temp_dir, "boss_home")
        self.orgs_config_dir = os.path.join(self.boss_home_dir, "config", "organizations")
        self.templates_dir = os.path.join(self.boss_home_dir, "templates", "organizations")
        self.orgs_data_dir = os.path.join(self.boss_home_dir, "data", "organizations")
        
        # Create required directories
        os.makedirs(self.boss_home_dir, exist_ok=True)
        os.makedirs(self.orgs_config_dir, exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(self.orgs_data_dir, exist_ok=True)
        
        # Create test template
        self.test_template_id = "test_template"
        self.test_template = {
            "settings": {
                "theme": "dark",
                "language": "en-US"
            },
            "resources": {
                "database": {
                    "type": "mysql",
                    "host": "localhost"
                }
            },
            "integrations": {
                "slack": {
                    "enabled": True,
                    "webhook_url": "https://hooks.slack.com/example"
                }
            },
            "permissions": {
                "admin": {
                    "can_manage_users": True,
                    "can_manage_resources": True
                },
                "user": {
                    "can_view_resources": True
                }
            }
        }
        
        template_file = os.path.join(self.templates_dir, f"{self.test_template_id}.json")
        with open(template_file, "w") as f:
            json.dump(self.test_template, f, indent=2)
            
        # Create template files directory
        template_files_dir = os.path.join(self.templates_dir, self.test_template_id)
        os.makedirs(template_files_dir, exist_ok=True)
        
        # Create sample file in template
        with open(os.path.join(template_files_dir, "readme.txt"), "w") as f:
            f.write("This is a template organization")
        
        # Mock environment variables
        self.env_patcher = patch.dict("os.environ", {
            "BOSS_HOME": self.boss_home_dir,
            "BOSS_CURRENT_ORG": "default"
        })
        self.env_patcher.start()
        
        # Create test resolver metadata
        self.metadata = TaskResolverMetadata(
            name="OrganizationSetupResolver",
            description="Test Resolver",
            version="1.0.0"
        )
        
        # Initialize the resolver
        self.resolver = OrganizationSetupResolver(self.metadata)
        
        # Create a test organization for some tests
        self.test_org_id = "test_org"
        self.test_org_name = "Test Organization"
        self.test_org_config = {
            "id": self.test_org_id,
            "name": self.test_org_name,
            "description": "Test organization for unit tests",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "settings": {},
            "contact_info": {},
            "integrations": {},
            "resources": {},
            "users": {},
            "permissions": {}
        }
        
        test_org_config_file = os.path.join(self.orgs_config_dir, f"{self.test_org_id}.json")
        with open(test_org_config_file, "w") as f:
            json.dump(self.test_org_config, f, indent=2)
            
        # Create organization directory structure
        test_org_dir = os.path.join(self.orgs_data_dir, self.test_org_id)
        os.makedirs(os.path.join(test_org_dir, "resources"), exist_ok=True)
        os.makedirs(os.path.join(test_org_dir, "users"), exist_ok=True)
        os.makedirs(os.path.join(test_org_dir, "integrations"), exist_ok=True)
    
    def tearDown(self) -> None:
        """Clean up after tests."""
        # Stop environment patch
        self.env_patcher.stop()
        
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def _create_task(self, input_data: Dict[str, Any]) -> Task:
        """Create a task with the given input data.
        
        Args:
            input_data: The input data for the task
            
        Returns:
            A task for testing
        """
        return Task(
            id="test_task",
            name="Test Organization Setup Task",
            description="A test task for organization setup operations",
            input_data=input_data,
            metadata=TaskMetadata(
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        )
    
    async def test_invalid_input(self) -> None:
        """Test handling of invalid input data."""
        # Create task with valid input first
        task = self._create_task({})
        
        # Manually modify input_data to a string after creation to bypass validation
        task.input_data = "not a dictionary"  # type: ignore
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("must be a dictionary", result.output_data.get("error", ""))
    
    async def test_missing_operation(self) -> None:
        """Test handling of missing operation."""
        task = self._create_task({})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'operation'", result.output_data.get("error", ""))
    
    async def test_invalid_operation(self) -> None:
        """Test handling of invalid operation."""
        task = self._create_task({"operation": "invalid_operation"})
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Unsupported operation", result.output_data.get("error", ""))
    
    async def test_create_organization(self) -> None:
        """Test creating an organization."""
        org_id = "new_org"
        org_name = "New Organization"
        
        task = self._create_task({
            "operation": "create_organization",
            "org_id": org_id,
            "name": org_name,
            "description": "A new test organization"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("created successfully", result.output_data.get("message", ""))
        
        # Verify organization was created
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        self.assertTrue(os.path.exists(org_config_file))
        
        # Verify organization directory structure was created
        org_dir = os.path.join(self.orgs_data_dir, org_id)
        self.assertTrue(os.path.exists(org_dir))
        self.assertTrue(os.path.exists(os.path.join(org_dir, "resources")))
        self.assertTrue(os.path.exists(os.path.join(org_dir, "users")))
        self.assertTrue(os.path.exists(os.path.join(org_dir, "integrations")))
        
        # Verify organization data
        with open(org_config_file, "r") as f:
            org_data = json.load(f)
            
        self.assertEqual(org_data["id"], org_id)
        self.assertEqual(org_data["name"], org_name)
    
    async def test_create_organization_with_template(self) -> None:
        """Test creating an organization with a template."""
        org_id = "template_org"
        org_name = "Template Organization"
        
        task = self._create_task({
            "operation": "create_organization",
            "org_id": org_id,
            "name": org_name,
            "description": "An organization created from a template",
            "template": self.test_template_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("created successfully", result.output_data.get("message", ""))
        
        # Verify organization was created with template data
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        with open(org_config_file, "r") as f:
            org_data = json.load(f)
            
        # Verify template settings were applied
        self.assertEqual(org_data["settings"]["theme"], "dark")
        self.assertEqual(org_data["settings"]["language"], "en-US")
        
        # Verify template resources were applied
        self.assertEqual(org_data["resources"]["database"]["type"], "mysql")
        
        # Verify template file was copied
        self.assertTrue(os.path.exists(os.path.join(self.orgs_data_dir, org_id, "readme.txt")))
    
    async def test_create_organization_missing_id(self) -> None:
        """Test creating an organization with missing ID."""
        task = self._create_task({
            "operation": "create_organization",
            "name": "Incomplete Organization"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'org_id'", result.output_data.get("error", ""))
    
    async def test_create_organization_missing_name(self) -> None:
        """Test creating an organization with missing name."""
        task = self._create_task({
            "operation": "create_organization",
            "org_id": "incomplete_org"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'name'", result.output_data.get("error", ""))
    
    async def test_create_organization_duplicate(self) -> None:
        """Test creating an organization with existing ID."""
        task = self._create_task({
            "operation": "create_organization",
            "org_id": self.test_org_id,
            "name": "Duplicate Organization"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("already exists", result.output_data.get("error", ""))
    
    async def test_update_organization(self) -> None:
        """Test updating an organization."""
        new_name = "Updated Test Organization"
        new_description = "Updated description"
        
        task = self._create_task({
            "operation": "update_organization",
            "org_id": self.test_org_id,
            "name": new_name,
            "description": new_description,
            "settings": {
                "theme": "light"
            }
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("updated successfully", result.output_data.get("message", ""))
        
        # Verify organization was updated
        org_config_file = os.path.join(self.orgs_config_dir, f"{self.test_org_id}.json")
        with open(org_config_file, "r") as f:
            org_data = json.load(f)
            
        self.assertEqual(org_data["name"], new_name)
        self.assertEqual(org_data["description"], new_description)
        self.assertEqual(org_data["settings"]["theme"], "light")
    
    async def test_update_organization_missing_id(self) -> None:
        """Test updating an organization with missing ID."""
        task = self._create_task({
            "operation": "update_organization",
            "name": "Updated Organization"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'org_id'", result.output_data.get("error", ""))
    
    async def test_update_organization_not_found(self) -> None:
        """Test updating a non-existent organization."""
        task = self._create_task({
            "operation": "update_organization",
            "org_id": "nonexistent_org",
            "name": "Nonexistent Organization"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
    
    async def test_list_organizations(self) -> None:
        """Test listing organizations."""
        # Create another test organization
        another_org_id = "another_org"
        another_org_config = {
            "id": another_org_id,
            "name": "Another Organization",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        another_org_config_file = os.path.join(self.orgs_config_dir, f"{another_org_id}.json")
        with open(another_org_config_file, "w") as f:
            json.dump(another_org_config, f, indent=2)
            
        task = self._create_task({
            "operation": "list_organizations"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("organizations", result.output_data)
        
        orgs = result.output_data.get("organizations", [])
        self.assertEqual(len(orgs), 2)
        
        # Verify organization IDs
        org_ids = [org.get("id") for org in orgs]
        self.assertIn(self.test_org_id, org_ids)
        self.assertIn(another_org_id, org_ids)
    
    async def test_get_organization(self) -> None:
        """Test getting organization details."""
        task = self._create_task({
            "operation": "get_organization",
            "org_id": self.test_org_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("organization", result.output_data)
        
        org_data = result.output_data.get("organization", {})
        self.assertEqual(org_data.get("id"), self.test_org_id)
        self.assertEqual(org_data.get("name"), self.test_org_name)
    
    async def test_get_organization_default(self) -> None:
        """Test getting the default organization when no ID is provided."""
        task = self._create_task({
            "operation": "get_organization"
        })
        
        # Since we're using "default" as the current org in the environment,
        # and it doesn't exist, we should get an error
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
        
        # Create the default organization
        default_org_config = {
            "id": "default",
            "name": "Default Organization",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        default_org_config_file = os.path.join(self.orgs_config_dir, "default.json")
        with open(default_org_config_file, "w") as f:
            json.dump(default_org_config, f, indent=2)
            
        # Try again
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("organization", result.output_data)
        
        org_data = result.output_data.get("organization", {})
        self.assertEqual(org_data.get("id"), "default")
    
    async def test_get_organization_not_found(self) -> None:
        """Test getting a non-existent organization."""
        task = self._create_task({
            "operation": "get_organization",
            "org_id": "nonexistent_org"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
    
    async def test_delete_organization(self) -> None:
        """Test deleting an organization."""
        # Create an organization to delete
        delete_org_id = "org_to_delete"
        delete_org_config = {
            "id": delete_org_id,
            "name": "Organization to Delete",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        delete_org_config_file = os.path.join(self.orgs_config_dir, f"{delete_org_id}.json")
        with open(delete_org_config_file, "w") as f:
            json.dump(delete_org_config, f, indent=2)
            
        delete_org_dir = os.path.join(self.orgs_data_dir, delete_org_id)
        os.makedirs(delete_org_dir, exist_ok=True)
        
        task = self._create_task({
            "operation": "delete_organization",
            "org_id": delete_org_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("deleted successfully", result.output_data.get("message", ""))
        
        # Verify organization was deleted
        self.assertFalse(os.path.exists(delete_org_config_file))
        self.assertFalse(os.path.exists(delete_org_dir))
    
    async def test_delete_organization_missing_id(self) -> None:
        """Test deleting an organization with missing ID."""
        task = self._create_task({
            "operation": "delete_organization"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'org_id'", result.output_data.get("error", ""))
    
    async def test_delete_organization_not_found(self) -> None:
        """Test deleting a non-existent organization."""
        task = self._create_task({
            "operation": "delete_organization",
            "org_id": "nonexistent_org"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
    
    async def test_delete_active_organization(self) -> None:
        """Test deleting the active organization."""
        # Make test_org the active organization
        os.environ["BOSS_CURRENT_ORG"] = self.test_org_id
        self.resolver.current_org = self.test_org_id
        
        task = self._create_task({
            "operation": "delete_organization",
            "org_id": self.test_org_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Cannot delete active organization", result.output_data.get("error", ""))
        
        # Try with force=true
        task = self._create_task({
            "operation": "delete_organization",
            "org_id": self.test_org_id,
            "force": True
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("deleted successfully", result.output_data.get("message", ""))
    
    async def test_set_active_organization(self) -> None:
        """Test setting the active organization."""
        task = self._create_task({
            "operation": "set_active_organization",
            "org_id": self.test_org_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("set as active", result.output_data.get("message", ""))
        
        # Verify current_org was updated
        self.assertEqual(self.resolver.current_org, self.test_org_id)
        self.assertEqual(os.environ["BOSS_CURRENT_ORG"], self.test_org_id)
        
        # Test with persist=true
        task = self._create_task({
            "operation": "set_active_organization",
            "org_id": self.test_org_id,
            "persist": True
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        
        # Verify the active org file was created
        active_org_file = os.path.join(self.boss_home_dir, "config", "active_org")
        self.assertTrue(os.path.exists(active_org_file))
        
        with open(active_org_file, "r") as f:
            active_org = f.read()
            
        self.assertEqual(active_org, self.test_org_id)
    
    async def test_set_active_organization_missing_id(self) -> None:
        """Test setting the active organization with missing ID."""
        task = self._create_task({
            "operation": "set_active_organization"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'org_id'", result.output_data.get("error", ""))
    
    async def test_set_active_organization_not_found(self) -> None:
        """Test setting a non-existent organization as active."""
        task = self._create_task({
            "operation": "set_active_organization",
            "org_id": "nonexistent_org"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("not found", result.output_data.get("error", ""))
    
    async def test_setup_resources(self) -> None:
        """Test setting up organization resources."""
        resources = {
            "database": {
                "type": "postgres",
                "host": "localhost",
                "port": 5432,
                "username": "boss",
                "password": "password"
            },
            "storage": {
                "type": "s3",
                "bucket": "boss-data"
            }
        }
        
        task = self._create_task({
            "operation": "setup_resources",
            "org_id": self.test_org_id,
            "resources": resources
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("Resources set up successfully", result.output_data.get("message", ""))
        
        # Verify resources were added to organization
        org_config_file = os.path.join(self.orgs_config_dir, f"{self.test_org_id}.json")
        with open(org_config_file, "r") as f:
            org_data = json.load(f)
            
        self.assertIn("database", org_data["resources"])
        self.assertIn("storage", org_data["resources"])
        
        # Verify resource files were created
        resources_dir = os.path.join(self.orgs_data_dir, self.test_org_id, "resources")
        self.assertTrue(os.path.exists(os.path.join(resources_dir, "database.json")))
        self.assertTrue(os.path.exists(os.path.join(resources_dir, "storage.json")))
    
    async def test_setup_resources_missing_resources(self) -> None:
        """Test setting up resources with missing resources data."""
        task = self._create_task({
            "operation": "setup_resources",
            "org_id": self.test_org_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'resources'", result.output_data.get("error", ""))
    
    async def test_setup_integrations(self) -> None:
        """Test setting up organization integrations."""
        integrations = {
            "github": {
                "enabled": True,
                "token": "github_token"
            },
            "jira": {
                "enabled": True,
                "url": "https://jira.example.com",
                "username": "jira_user",
                "token": "jira_token"
            }
        }
        
        task = self._create_task({
            "operation": "setup_integrations",
            "org_id": self.test_org_id,
            "integrations": integrations
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("Integrations set up successfully", result.output_data.get("message", ""))
        
        # Verify integrations were added to organization
        org_config_file = os.path.join(self.orgs_config_dir, f"{self.test_org_id}.json")
        with open(org_config_file, "r") as f:
            org_data = json.load(f)
            
        self.assertIn("github", org_data["integrations"])
        self.assertIn("jira", org_data["integrations"])
        
        # Verify integration files were created
        integrations_dir = os.path.join(self.orgs_data_dir, self.test_org_id, "integrations")
        self.assertTrue(os.path.exists(os.path.join(integrations_dir, "github.json")))
        self.assertTrue(os.path.exists(os.path.join(integrations_dir, "jira.json")))
    
    async def test_setup_integrations_missing_integrations(self) -> None:
        """Test setting up integrations with missing integrations data."""
        task = self._create_task({
            "operation": "setup_integrations",
            "org_id": self.test_org_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'integrations'", result.output_data.get("error", ""))
    
    async def test_create_user(self) -> None:
        """Test creating a user for an organization."""
        username = "testuser"
        display_name = "Test User"
        email = "test@example.com"
        
        task = self._create_task({
            "operation": "create_user",
            "org_id": self.test_org_id,
            "username": username,
            "display_name": display_name,
            "email": email,
            "role": "admin"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("created successfully", result.output_data.get("message", ""))
        
        # Verify user was added to organization
        org_config_file = os.path.join(self.orgs_config_dir, f"{self.test_org_id}.json")
        with open(org_config_file, "r") as f:
            org_data = json.load(f)
            
        self.assertIn(username, org_data["users"])
        self.assertEqual(org_data["users"][username]["display_name"], display_name)
        self.assertEqual(org_data["users"][username]["email"], email)
        self.assertEqual(org_data["users"][username]["role"], "admin")
        
        # Verify user file was created
        users_dir = os.path.join(self.orgs_data_dir, self.test_org_id, "users")
        self.assertTrue(os.path.exists(os.path.join(users_dir, f"{username}.json")))
    
    async def test_create_user_missing_username(self) -> None:
        """Test creating a user with missing username."""
        task = self._create_task({
            "operation": "create_user",
            "org_id": self.test_org_id,
            "display_name": "Incomplete User",
            "email": "incomplete@example.com"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'username'", result.output_data.get("error", ""))
    
    async def test_setup_permissions(self) -> None:
        """Test setting up permissions for an organization."""
        permissions = {
            "admin": {
                "can_manage_users": True,
                "can_manage_resources": True,
                "can_manage_integrations": True
            },
            "user": {
                "can_view_resources": True,
                "can_use_integrations": True
            },
            "guest": {
                "can_view_resources": False,
                "can_use_integrations": False
            }
        }
        
        task = self._create_task({
            "operation": "setup_permissions",
            "org_id": self.test_org_id,
            "permissions": permissions
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertIn("Permissions set up successfully", result.output_data.get("message", ""))
        
        # Verify permissions were added to organization
        org_config_file = os.path.join(self.orgs_config_dir, f"{self.test_org_id}.json")
        with open(org_config_file, "r") as f:
            org_data = json.load(f)
            
        self.assertIn("admin", org_data["permissions"])
        self.assertIn("user", org_data["permissions"])
        self.assertIn("guest", org_data["permissions"])
    
    async def test_setup_permissions_missing_permissions(self) -> None:
        """Test setting up permissions with missing permissions data."""
        task = self._create_task({
            "operation": "setup_permissions",
            "org_id": self.test_org_id
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.ERROR)
        self.assertIn("Missing 'permissions'", result.output_data.get("error", ""))
    
    async def test_health_check(self) -> None:
        """Test health check operation."""
        task = self._create_task({
            "operation": "health_check"
        })
        
        result = await self.resolver.resolve(task)
        
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_data.get("status"), "ok")
        self.assertEqual(result.output_data.get("config_check"), "ok")
        self.assertEqual(result.output_data.get("templates_check"), "ok")
        
        # Verify organization count
        self.assertGreaterEqual(result.output_data.get("organizations_count", 0), 1)
        
        # Verify active organization
        self.assertEqual(result.output_data.get("active_organization"), "default") 