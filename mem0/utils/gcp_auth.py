import os
import json
from typing import Optional, Dict, Any

try:
    from google.oauth2 import service_account
    from google.auth import default
    import google.auth.credentials
except ImportError:
    raise ImportError("google-auth is required for GCP authentication. Install with: pip install google-auth")


class GCPAuthenticator:
    """
    Centralized GCP authentication handler that supports multiple credential methods.

    Priority order:
    1. service_account_json (dict) - In-memory service account credentials
    2. credentials_path (str) - Path to service account JSON file
    3. Environment variables (GOOGLE_APPLICATION_CREDENTIALS)
    4. Default credentials (for environments like GCE, Cloud Run, etc.)
    """

    @staticmethod
    def get_credentials(
        service_account_json: Optional[Dict[str, Any]] = None,
        credentials_path: Optional[str] = None,
        scopes: Optional[list] = None
    ) -> tuple[google.auth.credentials.Credentials, Optional[str]]:
        """
        Get Google credentials using the priority order defined above.

        Args:
            service_account_json: Service account credentials as a dictionary
            credentials_path: Path to service account JSON file
            scopes: List of OAuth scopes (optional)

        Returns:
            tuple: (credentials, project_id)

        Raises:
            ValueError: If no valid credentials are found
        """
        credentials = None
        project_id = None

        # Method 1: Service account JSON (in-memory)
        if service_account_json:
            credentials = service_account.Credentials.from_service_account_info(
                service_account_json, scopes=scopes
            )
            project_id = service_account_json.get("project_id")

        # Method 2: Service account file path
        elif credentials_path and os.path.isfile(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=scopes
            )
            # Extract project_id from the file
            with open(credentials_path, 'r') as f:
                cred_data = json.load(f)
                project_id = cred_data.get("project_id")

        # Method 3: Environment variable path
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if os.path.isfile(env_path):
                credentials = service_account.Credentials.from_service_account_file(
                    env_path, scopes=scopes
                )
                # Extract project_id from the file
                with open(env_path, 'r') as f:
                    cred_data = json.load(f)
                    project_id = cred_data.get("project_id")

        # Method 4: Default credentials (GCE, Cloud Run, etc.)
        if not credentials:
            try:
                credentials, project_id = default(scopes=scopes)
            except Exception as e:
                raise ValueError(
                    f"No valid GCP credentials found. Please provide one of:\n"
                    f"1. service_account_json parameter (dict)\n"
                    f"2. credentials_path parameter (file path)\n"
                    f"3. GOOGLE_APPLICATION_CREDENTIALS environment variable\n"
                    f"4. Default credentials (if running on GCP)\n"
                    f"Error: {e}"
                )

        return credentials, project_id

    @staticmethod
    def setup_vertex_ai(
        service_account_json: Optional[Dict[str, Any]] = None,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
        location: str = "us-central1"
    ) -> str:
        """
        Initialize Vertex AI with proper authentication.

        Args:
            service_account_json: Service account credentials as dict
            credentials_path: Path to service account JSON file
            project_id: GCP project ID (optional, will be auto-detected)
            location: GCP location/region

        Returns:
            str: The project ID being used

        Raises:
            ValueError: If authentication fails
        """
        try:
            import vertexai
        except ImportError:
            raise ImportError("google-cloud-aiplatform is required for Vertex AI. Install with: pip install google-cloud-aiplatform")

        credentials, detected_project_id = GCPAuthenticator.get_credentials(
            service_account_json=service_account_json,
            credentials_path=credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        # Use provided project_id or fall back to detected one
        final_project_id = project_id or detected_project_id or os.getenv("GOOGLE_CLOUD_PROJECT")

        if not final_project_id:
            raise ValueError("Project ID could not be determined. Please provide project_id parameter or set GOOGLE_CLOUD_PROJECT environment variable.")

        vertexai.init(project=final_project_id, location=location, credentials=credentials)
        return final_project_id

    @staticmethod
    def get_genai_client(
        service_account_json: Optional[Dict[str, Any]] = None,
        credentials_path: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Get a Google GenAI client with authentication.

        Args:
            service_account_json: Service account credentials as dict
            credentials_path: Path to service account JSON file
            api_key: API key (takes precedence over service account)

        Returns:
            Google GenAI client instance
        """
        try:
            from google.genai import Client as GenAIClient
        except ImportError:
            raise ImportError("google-genai is required. Install with: pip install google-genai")

        # If API key is provided, use it directly
        if api_key:
            return GenAIClient(api_key=api_key)

        # Otherwise, try service account authentication
        credentials, _ = GCPAuthenticator.get_credentials(
            service_account_json=service_account_json,
            credentials_path=credentials_path,
            scopes=["https://www.googleapis.com/auth/generative-language"]
        )

        return GenAIClient(credentials=credentials)