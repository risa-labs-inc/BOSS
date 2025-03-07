"""OrganizationSetupResolver for configuring BOSS for new organizations.

This resolver handles the setup and configuration of BOSS instances for new organizations,
including creation of organization profiles, configuration of default settings,
and initialization of organization-specific resources.
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

from boss.core.task_models import Task, TaskResult
from boss.core.task_resolver import TaskResolver, TaskResolverMetadata
from boss.core.task_status import TaskStatus


class OrganizationSetupResolver(TaskResolver):
    """Resolver for handling organization setup operations.
    
    This resolver supports various setup operations including:
    - Organization profile creation
    - Default settings configuration
    - Resource initialization
    - User and permission setup
    - Integration configuration
    
    Attributes:
        boss_home_dir: The home directory of the BOSS instance
        orgs_config_dir: Directory for organization configurations
        templates_dir: Directory for organization templates
        current_org: The currently active organization ID
    """
    
    def __init__(self, metadata: TaskResolverMetadata) -> None:
        """Initialize the OrganizationSetupResolver.
        
        Args:
            metadata: Resolver metadata
        """
        super().__init__(metadata)
        self.boss_home_dir = os.environ.get("BOSS_HOME", os.getcwd())
        self.orgs_config_dir = os.path.join(self.boss_home_dir, "config", "organizations")
        self.templates_dir = os.path.join(self.boss_home_dir, "templates", "organizations")
        self.current_org = os.environ.get("BOSS_CURRENT_ORG", "default")
        
        # Ensure directories exist
        os.makedirs(self.orgs_config_dir, exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
    
    async def resolve(self, task: Task) -> TaskResult:
        """Resolve the organization setup task.
        
        Args:
            task: The organization setup task to resolve
            
        Returns:
            The task result with the outcome of the setup operation
        """
        try:
            if not isinstance(task.input_data, dict):
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Input data must be a dictionary"}
                )
            
            operation = task.input_data.get("operation")
            if not operation:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": "Missing 'operation' field in input data"}
                )
                
            # Handle different operations
            if operation == "create_organization":
                return await self._handle_create_organization(task)
            elif operation == "update_organization":
                return await self._handle_update_organization(task)
            elif operation == "list_organizations":
                return await self._handle_list_organizations(task)
            elif operation == "get_organization":
                return await self._handle_get_organization(task)
            elif operation == "delete_organization":
                return await self._handle_delete_organization(task)
            elif operation == "set_active_organization":
                return await self._handle_set_active_organization(task)
            elif operation == "setup_resources":
                return await self._handle_setup_resources(task)
            elif operation == "setup_integrations":
                return await self._handle_setup_integrations(task)
            elif operation == "create_user":
                return await self._handle_create_user(task)
            elif operation == "setup_permissions":
                return await self._handle_setup_permissions(task)
            elif operation == "health_check":
                return await self._handle_health_check(task)
            else:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"Unsupported operation: {operation}"}
                )
                
        except Exception as e:
            self.logger.error(f"Error in OrganizationSetupResolver: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": str(e)}
            )
    
    async def _handle_create_organization(self, task: Task) -> TaskResult:
        """Handle organization creation.
        
        Args:
            task: The organization creation task
            
        Returns:
            The result of the organization creation operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id")
        name = input_data.get("name")
        
        if not org_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'org_id' in input data"}
            )
            
        if not name:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'name' in input data"}
            )
            
        # Check if organization already exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' already exists"}
            )
            
        # Create organization configuration
        org_data = {
            "id": org_id,
            "name": name,
            "description": input_data.get("description", ""),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "settings": input_data.get("settings", {}),
            "contact_info": input_data.get("contact_info", {}),
            "integrations": input_data.get("integrations", {}),
            "resources": {},
            "users": {},
            "permissions": {}
        }
        
        # Write organization configuration to file
        try:
            with open(org_config_file, "w") as f:
                json.dump(org_data, f, indent=2)
                
            # Create organization directory structure
            org_dir = os.path.join(self.boss_home_dir, "data", "organizations", org_id)
            resources_dir = os.path.join(org_dir, "resources")
            users_dir = os.path.join(org_dir, "users")
            integrations_dir = os.path.join(org_dir, "integrations")
            
            os.makedirs(org_dir, exist_ok=True)
            os.makedirs(resources_dir, exist_ok=True)
            os.makedirs(users_dir, exist_ok=True)
            os.makedirs(integrations_dir, exist_ok=True)
            
            # Use template if specified
            template_id = input_data.get("template")
            if template_id:
                await self._apply_template(org_id, template_id)
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Organization '{name}' (ID: {org_id}) created successfully",
                    "organization": org_data
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error creating organization: {str(e)}")
            # Clean up any partially created files/directories
            if os.path.exists(org_config_file):
                os.remove(org_config_file)
                
            org_dir = os.path.join(self.boss_home_dir, "data", "organizations", org_id)
            if os.path.exists(org_dir):
                shutil.rmtree(org_dir)
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to create organization: {str(e)}"}
            )
    
    async def _handle_update_organization(self, task: Task) -> TaskResult:
        """Handle organization update.
        
        Args:
            task: The organization update task
            
        Returns:
            The result of the organization update operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id")
        
        if not org_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'org_id' in input data"}
            )
            
        # Check if organization exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if not os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' not found"}
            )
            
        # Read existing organization configuration
        try:
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            # Update fields
            if "name" in input_data:
                org_data["name"] = input_data["name"]
                
            if "description" in input_data:
                org_data["description"] = input_data["description"]
                
            if "settings" in input_data:
                org_data["settings"].update(input_data["settings"])
                
            if "contact_info" in input_data:
                org_data["contact_info"].update(input_data["contact_info"])
                
            if "integrations" in input_data:
                org_data["integrations"].update(input_data["integrations"])
                
            # Update timestamp
            org_data["updated_at"] = datetime.now().isoformat()
            
            # Write updated configuration back to file
            with open(org_config_file, "w") as f:
                json.dump(org_data, f, indent=2)
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Organization '{org_data['name']}' (ID: {org_id}) updated successfully",
                    "organization": org_data
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error updating organization: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to update organization: {str(e)}"}
            )
    
    async def _handle_list_organizations(self, task: Task) -> TaskResult:
        """Handle listing organizations.
        
        Args:
            task: The list organizations task
            
        Returns:
            The result with list of organizations
        """
        try:
            organizations = []
            for filename in os.listdir(self.orgs_config_dir):
                if filename.endswith(".json"):
                    org_path = os.path.join(self.orgs_config_dir, filename)
                    with open(org_path, "r") as f:
                        org_data = json.load(f)
                        # Only include essential info in the list
                        organizations.append({
                            "id": org_data["id"],
                            "name": org_data["name"],
                            "description": org_data.get("description", ""),
                            "created_at": org_data.get("created_at"),
                            "updated_at": org_data.get("updated_at")
                        })
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "organizations": organizations,
                    "count": len(organizations),
                    "active_org": self.current_org
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error listing organizations: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to list organizations: {str(e)}"}
            )
    
    async def _handle_get_organization(self, task: Task) -> TaskResult:
        """Handle getting organization details.
        
        Args:
            task: The get organization task
            
        Returns:
            The result with organization details
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id", self.current_org)
        
        # Check if organization exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if not os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' not found"}
            )
            
        # Read organization configuration
        try:
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "organization": org_data,
                    "is_active": org_id == self.current_org
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error getting organization details: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to get organization details: {str(e)}"}
            )
    
    async def _handle_delete_organization(self, task: Task) -> TaskResult:
        """Handle organization deletion.
        
        Args:
            task: The delete organization task
            
        Returns:
            The result of the organization deletion operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id")
        force = input_data.get("force", False)
        
        if not org_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'org_id' in input data"}
            )
            
        # Check if organization exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if not os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' not found"}
            )
            
        # Check if this is the active organization
        if org_id == self.current_org and not force:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={
                    "error": f"Cannot delete active organization. Set another organization as active first or use 'force=true'."
                }
            )
            
        # Delete organization
        try:
            # Read organization info for the result message
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            org_name = org_data.get("name", org_id)
            
            # Delete configuration file
            os.remove(org_config_file)
            
            # Delete organization directory
            org_dir = os.path.join(self.boss_home_dir, "data", "organizations", org_id)
            if os.path.exists(org_dir):
                shutil.rmtree(org_dir)
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Organization '{org_name}' (ID: {org_id}) deleted successfully"
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error deleting organization: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to delete organization: {str(e)}"}
            )
    
    async def _handle_set_active_organization(self, task: Task) -> TaskResult:
        """Handle setting the active organization.
        
        Args:
            task: The set active organization task
            
        Returns:
            The result of the operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id")
        persist = input_data.get("persist", False)
        
        if not org_id:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'org_id' in input data"}
            )
            
        # Check if organization exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if not os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' not found"}
            )
            
        # Set as active
        try:
            # Read organization info
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            org_name = org_data.get("name", org_id)
            
            # Update current org
            self.current_org = org_id
            os.environ["BOSS_CURRENT_ORG"] = org_id
            
            # Persist if requested
            if persist:
                active_org_file = os.path.join(self.boss_home_dir, "config", "active_org")
                with open(active_org_file, "w") as f:
                    f.write(org_id)
                    
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Organization '{org_name}' (ID: {org_id}) set as active",
                    "persisted": persist
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error setting active organization: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to set active organization: {str(e)}"}
            )
    
    async def _handle_setup_resources(self, task: Task) -> TaskResult:
        """Handle setting up organization resources.
        
        Args:
            task: The setup resources task
            
        Returns:
            The result of the resource setup operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id", self.current_org)
        resources = input_data.get("resources", {})
        
        if not resources:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'resources' in input data"}
            )
            
        # Check if organization exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if not os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' not found"}
            )
            
        # Set up resources
        try:
            # Read organization info
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            # Update resources
            if "resources" not in org_data:
                org_data["resources"] = {}
                
            org_data["resources"].update(resources)
            org_data["updated_at"] = datetime.now().isoformat()
            
            # Write updated configuration back to file
            with open(org_config_file, "w") as f:
                json.dump(org_data, f, indent=2)
                
            # Create resource files if needed
            resources_dir = os.path.join(
                self.boss_home_dir, "data", "organizations", org_id, "resources"
            )
            os.makedirs(resources_dir, exist_ok=True)
            
            for resource_name, resource_data in resources.items():
                resource_file = os.path.join(resources_dir, f"{resource_name}.json")
                with open(resource_file, "w") as f:
                    json.dump(resource_data, f, indent=2)
                    
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Resources set up successfully for organization '{org_id}'",
                    "resources": list(resources.keys())
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error setting up resources: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to set up resources: {str(e)}"}
            )
    
    async def _handle_setup_integrations(self, task: Task) -> TaskResult:
        """Handle setting up organization integrations.
        
        Args:
            task: The setup integrations task
            
        Returns:
            The result of the integration setup operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id", self.current_org)
        integrations = input_data.get("integrations", {})
        
        if not integrations:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'integrations' in input data"}
            )
            
        # Check if organization exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if not os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' not found"}
            )
            
        # Set up integrations
        try:
            # Read organization info
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            # Update integrations
            if "integrations" not in org_data:
                org_data["integrations"] = {}
                
            org_data["integrations"].update(integrations)
            org_data["updated_at"] = datetime.now().isoformat()
            
            # Write updated configuration back to file
            with open(org_config_file, "w") as f:
                json.dump(org_data, f, indent=2)
                
            # Create integration files if needed
            integrations_dir = os.path.join(
                self.boss_home_dir, "data", "organizations", org_id, "integrations"
            )
            os.makedirs(integrations_dir, exist_ok=True)
            
            for integration_name, integration_data in integrations.items():
                integration_file = os.path.join(integrations_dir, f"{integration_name}.json")
                with open(integration_file, "w") as f:
                    json.dump(integration_data, f, indent=2)
                    
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Integrations set up successfully for organization '{org_id}'",
                    "integrations": list(integrations.keys())
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error setting up integrations: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to set up integrations: {str(e)}"}
            )
    
    async def _handle_create_user(self, task: Task) -> TaskResult:
        """Handle creating a user for an organization.
        
        Args:
            task: The create user task
            
        Returns:
            The result of the user creation operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id", self.current_org)
        username = input_data.get("username")
        display_name = input_data.get("display_name", username)
        role = input_data.get("role", "user")
        
        if not username:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'username' in input data"}
            )
            
        # Check if organization exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if not os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' not found"}
            )
            
        # Create user
        try:
            # Read organization info
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            # Check if user already exists
            if "users" not in org_data:
                org_data["users"] = {}
                
            if username in org_data["users"]:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.ERROR,
                    output_data={"error": f"User '{username}' already exists in organization '{org_id}'"}
                )
                
            # Create user data
            user_data = {
                "username": username,
                "display_name": display_name,
                "role": role,
                "email": input_data.get("email", ""),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "settings": input_data.get("settings", {}),
                "active": input_data.get("active", True)
            }
            
            # Add user to organization
            org_data["users"][username] = user_data
            org_data["updated_at"] = datetime.now().isoformat()
            
            # Write updated configuration back to file
            with open(org_config_file, "w") as f:
                json.dump(org_data, f, indent=2)
                
            # Create user directory and file
            users_dir = os.path.join(
                self.boss_home_dir, "data", "organizations", org_id, "users"
            )
            os.makedirs(users_dir, exist_ok=True)
            
            user_file = os.path.join(users_dir, f"{username}.json")
            with open(user_file, "w") as f:
                json.dump(user_data, f, indent=2)
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"User '{username}' created successfully in organization '{org_id}'",
                    "user": user_data
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error creating user: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to create user: {str(e)}"}
            )
    
    async def _handle_setup_permissions(self, task: Task) -> TaskResult:
        """Handle setting up permissions for an organization.
        
        Args:
            task: The setup permissions task
            
        Returns:
            The result of the permission setup operation
        """
        input_data = cast(Dict[str, Any], task.input_data)
        org_id = input_data.get("org_id", self.current_org)
        permissions = input_data.get("permissions", {})
        
        if not permissions:
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": "Missing 'permissions' in input data"}
            )
            
        # Check if organization exists
        org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
        if not os.path.exists(org_config_file):
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Organization with ID '{org_id}' not found"}
            )
            
        # Set up permissions
        try:
            # Read organization info
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            # Update permissions
            if "permissions" not in org_data:
                org_data["permissions"] = {}
                
            # Process permissions structure
            for role, role_permissions in permissions.items():
                if role not in org_data["permissions"]:
                    org_data["permissions"][role] = {}
                    
                # Update permissions for this role
                org_data["permissions"][role].update(role_permissions)
                
            org_data["updated_at"] = datetime.now().isoformat()
            
            # Write updated configuration back to file
            with open(org_config_file, "w") as f:
                json.dump(org_data, f, indent=2)
                
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "message": f"Permissions set up successfully for organization '{org_id}'",
                    "roles_updated": list(permissions.keys())
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error setting up permissions: {str(e)}")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.ERROR,
                output_data={"error": f"Failed to set up permissions: {str(e)}"}
            )
    
    async def _handle_health_check(self, task: Task) -> TaskResult:
        """Perform a health check on the resolver.
        
        Args:
            task: The health check task
            
        Returns:
            The result of the health check
        """
        # Check if configuration directories exist
        config_check = "ok"
        config_reason = ""
        
        try:
            # Check if we can access the organizations directory
            if not os.path.exists(self.orgs_config_dir):
                os.makedirs(self.orgs_config_dir, exist_ok=True)
                
            # Check if we can write to it
            test_file = os.path.join(self.orgs_config_dir, "health_check_test.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
                
        except Exception as e:
            config_check = "fail"
            config_reason = str(e)
            
        # Check if templates directory exists
        templates_check = "ok"
        templates_reason = ""
        
        try:
            if not os.path.exists(self.templates_dir):
                os.makedirs(self.templates_dir, exist_ok=True)
                
        except Exception as e:
            templates_check = "fail"
            templates_reason = str(e)
            
        # Count organizations
        org_count = 0
        try:
            org_count = len([f for f in os.listdir(self.orgs_config_dir) if f.endswith(".json")])
        except Exception:
            pass
            
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            output_data={
                "status": "ok" if config_check == "ok" and templates_check == "ok" else "fail",
                "config_check": config_check,
                "config_reason": config_reason,
                "templates_check": templates_check,
                "templates_reason": templates_reason,
                "organizations_count": org_count,
                "active_organization": self.current_org
            }
        )
    
    async def _apply_template(self, org_id: str, template_id: str) -> bool:
        """Apply an organization template to a new organization.
        
        Args:
            org_id: The organization ID to apply the template to
            template_id: The template ID to apply
            
        Returns:
            True if template was applied successfully, False otherwise
        """
        template_file = os.path.join(self.templates_dir, f"{template_id}.json")
        if not os.path.exists(template_file):
            self.logger.error(f"Template '{template_id}' not found")
            return False
            
        try:
            # Read template
            with open(template_file, "r") as f:
                template_data = json.load(f)
                
            # Read organization config
            org_config_file = os.path.join(self.orgs_config_dir, f"{org_id}.json")
            with open(org_config_file, "r") as f:
                org_data = json.load(f)
                
            # Apply template settings
            if "settings" in template_data:
                if "settings" not in org_data:
                    org_data["settings"] = {}
                org_data["settings"].update(template_data["settings"])
                
            # Apply template resources
            if "resources" in template_data:
                if "resources" not in org_data:
                    org_data["resources"] = {}
                org_data["resources"].update(template_data["resources"])
                
            # Apply template integrations
            if "integrations" in template_data:
                if "integrations" not in org_data:
                    org_data["integrations"] = {}
                org_data["integrations"].update(template_data["integrations"])
                
            # Apply template permissions
            if "permissions" in template_data:
                if "permissions" not in org_data:
                    org_data["permissions"] = {}
                org_data["permissions"].update(template_data["permissions"])
                
            # Write updated organization config
            with open(org_config_file, "w") as f:
                json.dump(org_data, f, indent=2)
                
            # Apply template files if they exist
            template_files_dir = os.path.join(self.templates_dir, template_id)
            if os.path.exists(template_files_dir) and os.path.isdir(template_files_dir):
                org_dir = os.path.join(self.boss_home_dir, "data", "organizations", org_id)
                
                # Copy template files to organization directory
                for root, dirs, files in os.walk(template_files_dir):
                    for directory in dirs:
                        src_dir = os.path.join(root, directory)
                        rel_path = os.path.relpath(src_dir, template_files_dir)
                        dst_dir = os.path.join(org_dir, rel_path)
                        os.makedirs(dst_dir, exist_ok=True)
                        
                    for file in files:
                        src_file = os.path.join(root, file)
                        rel_path = os.path.relpath(src_file, template_files_dir)
                        dst_file = os.path.join(org_dir, rel_path)
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.copy2(src_file, dst_file)
                        
            return True
            
        except Exception as e:
            self.logger.error(f"Error applying template: {str(e)}")
            return False 