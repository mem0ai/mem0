import subprocess
import sys
from typing import Optional, ClassVar, Dict, Any

from pydantic import BaseModel, Field, model_validator

def ensure_chromadb_installed():
    """
    Ensure that the 'chromadb' library is installed. If not, prompt the user to install it.
    Returns:
        Client: The chromadb client class if installed successfully.
    """
    try:
        from chromadb.api.client import Client
        return Client
    except ImportError:
        user_input = input("The 'chromadb' library is required. Install it now? [y/N]: ")
        if user_input.lower() == 'y':
            try:
                print("Installing 'chromadb'...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "chromadb"])
                from chromadb.api.client import Client
                print("Successfully installed 'chromadb'.")
                return Client
            except subprocess.CalledProcessError:
                print("Failed to install 'chromadb'. Please install it manually.")
                sys.exit(1)
        else:
            raise ImportError("The required 'chromadb' library is not installed.")

class ChromaDbConfig(BaseModel):
    Client: ClassVar[type] = ensure_chromadb_installed()

    collection_name: str = Field("mem0", description="Default name for the collection")
    client: Optional[Client] = Field(
        None, description="Existing ChromaDB client instance"
    )
    path: Optional[str] = Field(None, description="Path to the database directory")
    host: Optional[str] = Field(None, description="Database connection remote host")
    port: Optional[int] = Field(None, description="Database connection remote port")

    @model_validator(mode="before")
    def check_host_port_or_path(cls, values):
        host, port, path = values.get("host"), values.get("port"), values.get("path")
        if not path and not (host and port):
            raise ValueError("Either 'host' and 'port' or 'path' must be provided.")
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = {
        "arbitrary_types_allowed": True,
    }
