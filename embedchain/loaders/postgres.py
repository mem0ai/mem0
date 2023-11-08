from typing import Optional, Dict, Any
import logging
import hashlib

from embedchain.loaders.base_loader import BaseLoader

class PostgresLoader(BaseLoader):
    
    def __init__(self):
        super().__init__()
        self.connection = None
        self.cursor = None
    
    def setup_loader(self, config: Optional[Dict[str, Any]] = None):
        if not config:
            raise ValueError(
                f"Must provide the valid config. Received: {config}"
            )
        
        try:
            import psycopg
        except:
            raise ImportError(
                "Unable to import required packages. \
                    Run `pip install --upgrade 'embedchain[postgres]'`"
            )
        
        config_info = ""
        if ('url' in config):
            config_info = config.get('url')
        else:
            conn_params = []
            for (key, value) in config.items():
                conn_params.append(f"{key}={value}")
            config_info = " ".join(conn_params)
        
        logging.info(f"Connecting to postrgres sql: {config_info}")
        self.connection = psycopg.connect(
            conninfo=config_info
        )
        self.cursor = self.connection.cursor()
            
    
    def load_data(self, query):
        if not self.cursor:
            raise ValueError("PostgreLoader cursor is not initialized. Call setup_loader first.")
        
        try:
            data = []
            data_content = []
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            for result in results:
                doc_content = str(result)
                data.append({"content": doc_content, "meta_data": {"url": f"postgres_query-({query})"}})
                data_content.append(doc_content)
            doc_id = hashlib.sha256((query + ", ".join(data_content)).encode()).hexdigest()
            return {
                "doc_id": doc_id,
                "data": data,
            }
        except Exception as e:
            raise ValueError(f"Failed to load data using query={query} with: {e}")
    
    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
