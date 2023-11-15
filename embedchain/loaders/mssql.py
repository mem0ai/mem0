from typing import Optional, Dict, Any
from embedchain.loaders.base_loader import BaseLoader

class MSSQLLoader(BaseLoader):
    """Loader for MSSQL data."""
    
    def __init__(self, config: Optional[Dict[str, Any]]):
        super().__init__()
        if not config:
            raise ValueError(
                f"Invalid MSSQL config: {config}.",
                "Provide the correct config, refer `https://docs.embedchain.ai/data-sources/mssql`.",
            )
        
        self.config = config
        self.connection = None
        self.cursor = None
        self._setup_loader(config=config)
    
    def _setup_loader(self, config: Dict[str, Any]):
        try:
            import pyodbc
        except ImportError as e:
            raise ImportError(
                "Unable to import required packages for MSSQL loader. Run `pip install --upgrade 'embedchain[mssql]'`."  # noqa: E501
            ) from e
        
        try:
            self.connection = pyodbc.connect(**config)
            self.cursor = self.connection.cursor()
        except Exception as e:
            raise ValueError(
                f"Unable to connect to MSSQL server with the given config: {config}.", # noqa: E501
            )
    
    def load_data():
        pass