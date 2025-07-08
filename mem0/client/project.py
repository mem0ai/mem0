import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from mem0.memory.telemetry import capture_client_event
from mem0.client.utils import api_error_handler

logger = logging.getLogger(__name__)


class ProjectConfig(BaseModel):
    """
    Configuration for project management operations.
    """

    org_id: Optional[str] = Field(
        default=None,
        description="Organization ID"
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Project ID"
    )
    user_email: Optional[str] = Field(
        default=None,
        description="User email"
    )

    class Config:
        validate_assignment = True
        extra = "forbid"


class BaseProject(ABC):
    """
    Abstract base class for project management operations.
    """

    def __init__(
        self,
        client: Any,
        config: Optional[ProjectConfig] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ):
        """
        Initialize the project manager.

        Args:
            client: HTTP client instance
            config: Project manager configuration
            org_id: Organization ID
            project_id: Project ID
            user_email: User email
        """
        self._client = client

        # Handle config initialization
        if config is not None:
            self.config = config
        else:
            # Create config from parameters
            self.config = ProjectConfig(
                org_id=org_id,
                project_id=project_id,
                user_email=user_email
            )

    @property
    def org_id(self) -> Optional[str]:
        """Get the organization ID."""
        return self.config.org_id

    @property
    def project_id(self) -> Optional[str]:
        """Get the project ID."""
        return self.config.project_id

    @property
    def user_email(self) -> Optional[str]:
        """Get the user email."""
        return self.config.user_email

    def _validate_org_project(self) -> None:
        """
        Validate that both org_id and project_id are set.

        Raises:
            ValueError: If org_id or project_id are not set.
        """
        if not (self.config.org_id and self.config.project_id):
            raise ValueError(
                "org_id and project_id must be set to access project operations"
            )

    def _prepare_params(
        self, kwargs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare query parameters for API requests.

        Args:
            kwargs: Additional keyword arguments.

        Returns:
            Dictionary containing prepared parameters.

        Raises:
            ValueError: If org_id or project_id validation fails.
        """
        if kwargs is None:
            kwargs = {}

        # Add org_id and project_id if available
        if self.config.org_id and self.config.project_id:
            kwargs["org_id"] = self.config.org_id
            kwargs["project_id"] = self.config.project_id
        elif self.config.org_id or self.config.project_id:
            raise ValueError("Please provide both org_id and project_id")

        return {k: v for k, v in kwargs.items() if v is not None}

    def _prepare_org_params(
        self, kwargs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare query parameters for organization-level API requests.

        Args:
            kwargs: Additional keyword arguments.

        Returns:
            Dictionary containing prepared parameters.

        Raises:
            ValueError: If org_id is not provided.
        """
        if kwargs is None:
            kwargs = {}

        # Add org_id if available
        if self.config.org_id:
            kwargs["org_id"] = self.config.org_id
        else:
            raise ValueError("org_id must be set for organization-level operations")

        return {k: v for k, v in kwargs.items() if v is not None}

    @abstractmethod
    def get(self, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get project details.

        Args:
            fields: List of fields to retrieve

        Returns:
            Dictionary containing the requested project fields.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        pass

    @abstractmethod
    def create(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new project within the organization.

        Args:
            name: Name of the project to be created
            description: Optional description for the project

        Returns:
            Dictionary containing the created project details.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id is not set.
        """
        pass

    @abstractmethod
    def update(
        self,
        custom_instructions: Optional[str] = None,
        custom_categories: Optional[List[str]] = None,
        retrieval_criteria: Optional[List[Dict[str, Any]]] = None,
        enable_graph: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update project settings.

        Args:
            custom_instructions: New instructions for the project
            custom_categories: New categories for the project
            retrieval_criteria: New retrieval criteria for the project
            enable_graph: Enable or disable the graph for the project

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        pass

    @abstractmethod
    def delete(self) -> Dict[str, Any]:
        """
        Delete the current project and its related data.

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        pass

    @abstractmethod
    def get_members(self) -> Dict[str, Any]:
        """
        Get all members of the current project.

        Returns:
            Dictionary containing the list of project members.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        pass

    @abstractmethod
    def add_member(self, email: str, role: str = "READER") -> Dict[str, Any]:
        """
        Add a new member to the current project.

        Args:
            email: Email address of the user to add
            role: Role to assign ("READER" or "OWNER")

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        pass

    @abstractmethod
    def update_member(self, email: str, role: str) -> Dict[str, Any]:
        """
        Update a member's role in the current project.

        Args:
            email: Email address of the user to update
            role: New role to assign ("READER" or "OWNER")

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        pass

    @abstractmethod
    def remove_member(self, email: str) -> Dict[str, Any]:
        """
        Remove a member from the current project.

        Args:
            email: Email address of the user to remove

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        pass


class Project(BaseProject):
    """
    Synchronous project management operations.
    """

    def __init__(
        self,
        client: httpx.Client,
        config: Optional[ProjectConfig] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ):
        """
        Initialize the synchronous project manager.

        Args:
            client: HTTP client instance
            config: Project manager configuration
            org_id: Organization ID
            project_id: Project ID
            user_email: User email
        """
        super().__init__(client, config, org_id, project_id, user_email)
        self._validate_org_project()

    @api_error_handler
    def get(self, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get project details.

        Args:
            fields: List of fields to retrieve

        Returns:
            Dictionary containing the requested project fields.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        params = self._prepare_params({"fields": fields})
        response = self._client.get(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/",
            params=params,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.get",
            self,
            {"fields": fields, "sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def create(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new project within the organization.

        Args:
            name: Name of the project to be created
            description: Optional description for the project

        Returns:
            Dictionary containing the created project details.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id is not set.
        """
        if not self.config.org_id:
            raise ValueError("org_id must be set to create a project")

        payload = {"name": name}
        if description is not None:
            payload["description"] = description

        response = self._client.post(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.create",
            self,
            {"name": name, "description": description, "sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def update(
        self,
        custom_instructions: Optional[str] = None,
        custom_categories: Optional[List[str]] = None,
        retrieval_criteria: Optional[List[Dict[str, Any]]] = None,
        enable_graph: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update project settings.

        Args:
            custom_instructions: New instructions for the project
            custom_categories: New categories for the project
            retrieval_criteria: New retrieval criteria for the project
            enable_graph: Enable or disable the graph for the project

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        if (
            custom_instructions is None
            and custom_categories is None
            and retrieval_criteria is None
            and enable_graph is None
        ):
            raise ValueError(
                "At least one parameter must be provided for update: "
                "custom_instructions, custom_categories, retrieval_criteria, "
                "enable_graph"
            )

        payload = self._prepare_params(
            {
                "custom_instructions": custom_instructions,
                "custom_categories": custom_categories,
                "retrieval_criteria": retrieval_criteria,
                "enable_graph": enable_graph
            }
        )
        response = self._client.patch(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.update",
            self,
            {
                "custom_instructions": custom_instructions,
                "custom_categories": custom_categories,
                "retrieval_criteria": retrieval_criteria,
                "enable_graph": enable_graph,
                "sync_type": "sync",
            },
        )
        return response.json()

    @api_error_handler
    def delete(self) -> Dict[str, Any]:
        """
        Delete the current project and its related data.

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        response = self._client.delete(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/",
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.delete",
            self,
            {"sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def get_members(self) -> Dict[str, Any]:
        """
        Get all members of the current project.

        Returns:
            Dictionary containing the list of project members.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        response = self._client.get(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/members/",
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.get_members",
            self,
            {"sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def add_member(self, email: str, role: str = "READER") -> Dict[str, Any]:
        """
        Add a new member to the current project.

        Args:
            email: Email address of the user to add
            role: Role to assign ("READER" or "OWNER")

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        if role not in ["READER", "OWNER"]:
            raise ValueError("Role must be either 'READER' or 'OWNER'")

        payload = {"email": email, "role": role}

        response = self._client.post(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/members/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.add_member",
            self,
            {"email": email, "role": role, "sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def update_member(self, email: str, role: str) -> Dict[str, Any]:
        """
        Update a member's role in the current project.

        Args:
            email: Email address of the user to update
            role: New role to assign ("READER" or "OWNER")

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        if role not in ["READER", "OWNER"]:
            raise ValueError("Role must be either 'READER' or 'OWNER'")

        payload = {"email": email, "role": role}

        response = self._client.put(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/members/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.update_member",
            self,
            {"email": email, "role": role, "sync_type": "sync"},
        )
        return response.json()

    @api_error_handler
    def remove_member(self, email: str) -> Dict[str, Any]:
        """
        Remove a member from the current project.

        Args:
            email: Email address of the user to remove

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        params = {"email": email}

        response = self._client.delete(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/members/",
            params=params,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.remove_member",
            self,
            {"email": email, "sync_type": "sync"},
        )
        return response.json()


class AsyncProject(BaseProject):
    """
    Asynchronous project management operations.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        config: Optional[ProjectConfig] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ):
        """
        Initialize the asynchronous project manager.

        Args:
            client: HTTP client instance
            config: Project manager configuration
            org_id: Organization ID
            project_id: Project ID
            user_email: User email
        """
        super().__init__(client, config, org_id, project_id, user_email)
        self._validate_org_project()

    @api_error_handler
    async def get(self, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get project details.

        Args:
            fields: List of fields to retrieve

        Returns:
            Dictionary containing the requested project fields.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        params = self._prepare_params({"fields": fields})
        response = await self._client.get(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/",
            params=params,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.get",
            self,
            {"fields": fields, "sync_type": "async"},
        )
        return response.json()

    @api_error_handler
    async def create(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new project within the organization.

        Args:
            name: Name of the project to be created
            description: Optional description for the project

        Returns:
            Dictionary containing the created project details.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id is not set.
        """
        if not self.config.org_id:
            raise ValueError("org_id must be set to create a project")

        payload = {"name": name}
        if description is not None:
            payload["description"] = description

        response = await self._client.post(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.create",
            self,
            {"name": name, "description": description, "sync_type": "async"},
        )
        return response.json()

    @api_error_handler
    async def update(
        self,
        custom_instructions: Optional[str] = None,
        custom_categories: Optional[List[str]] = None,
        retrieval_criteria: Optional[List[Dict[str, Any]]] = None,
        enable_graph: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update project settings.

        Args:
            custom_instructions: New instructions for the project
            custom_categories: New categories for the project
            retrieval_criteria: New retrieval criteria for the project
            enable_graph: Enable or disable the graph for the project

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        if (
            custom_instructions is None
            and custom_categories is None
            and retrieval_criteria is None
            and enable_graph is None
        ):
            raise ValueError(
                "At least one parameter must be provided for update: "
                "custom_instructions, custom_categories, retrieval_criteria, "
                "enable_graph"
            )

        payload = self._prepare_params(
            {
                "custom_instructions": custom_instructions,
                "custom_categories": custom_categories,
                "retrieval_criteria": retrieval_criteria,
                "enable_graph": enable_graph
            }
        )
        response = await self._client.patch(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.update",
            self,
            {
                "custom_instructions": custom_instructions,
                "custom_categories": custom_categories,
                "retrieval_criteria": retrieval_criteria,
                "enable_graph": enable_graph,
                "sync_type": "async",
            },
        )
        return response.json()

    @api_error_handler
    async def delete(self) -> Dict[str, Any]:
        """
        Delete the current project and its related data.

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        response = await self._client.delete(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/",
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.delete",
            self,
            {"sync_type": "async"},
        )
        return response.json()

    @api_error_handler
    async def get_members(self) -> Dict[str, Any]:
        """
        Get all members of the current project.

        Returns:
            Dictionary containing the list of project members.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        response = await self._client.get(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/members/",
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.get_members",
            self,
            {"sync_type": "async"},
        )
        return response.json()

    @api_error_handler
    async def add_member(self, email: str, role: str = "READER") -> Dict[str, Any]:
        """
        Add a new member to the current project.

        Args:
            email: Email address of the user to add
            role: Role to assign ("READER" or "OWNER")

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        if role not in ["READER", "OWNER"]:
            raise ValueError("Role must be either 'READER' or 'OWNER'")

        payload = {"email": email, "role": role}

        response = await self._client.post(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/members/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.add_member",
            self,
            {"email": email, "role": role, "sync_type": "async"},
        )
        return response.json()

    @api_error_handler
    async def update_member(self, email: str, role: str) -> Dict[str, Any]:
        """
        Update a member's role in the current project.

        Args:
            email: Email address of the user to update
            role: New role to assign ("READER" or "OWNER")

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        if role not in ["READER", "OWNER"]:
            raise ValueError("Role must be either 'READER' or 'OWNER'")

        payload = {"email": email, "role": role}

        response = await self._client.put(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/members/",
            json=payload,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.update_member",
            self,
            {"email": email, "role": role, "sync_type": "async"},
        )
        return response.json()

    @api_error_handler
    async def remove_member(self, email: str) -> Dict[str, Any]:
        """
        Remove a member from the current project.

        Args:
            email: Email address of the user to remove

        Returns:
            Dictionary containing the API response.

        Raises:
            APIError: If the API request fails.
            ValueError: If org_id or project_id are not set.
        """
        params = {"email": email}

        response = await self._client.delete(
            f"/api/v1/orgs/organizations/{self.config.org_id}/projects/{self.config.project_id}/members/",
            params=params,
        )
        response.raise_for_status()
        capture_client_event(
            "client.project.remove_member",
            self,
            {"email": email, "sync_type": "async"},
        )
        return response.json()
