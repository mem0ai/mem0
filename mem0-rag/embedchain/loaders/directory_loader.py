import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

from embedchain.config import AddConfig
from embedchain.data_formatter.data_formatter import DataFormatter
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.loaders.text_file import TextFileLoader
from embedchain.utils.misc import detect_datatype

logger = logging.getLogger(__name__)


@register_deserializable
class DirectoryLoader(BaseLoader):
    """Load data from a directory."""

    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__()
        config = config or {}
        self.recursive = config.get("recursive", True)
        self.extensions = config.get("extensions", None)
        self.errors = []

    def load_data(self, path: str):
        directory_path = Path(path)
        if not directory_path.is_dir():
            raise ValueError(f"Invalid path: {path}")

        logger.info(f"Loading data from directory: {path}")
        data_list = self._process_directory(directory_path)
        doc_id = hashlib.sha256((str(data_list) + str(directory_path)).encode()).hexdigest()

        for error in self.errors:
            logger.warning(error)

        return {"doc_id": doc_id, "data": data_list}

    def _process_directory(self, directory_path: Path):
        data_list = []
        for file_path in directory_path.rglob("*") if self.recursive else directory_path.glob("*"):
            # don't include dotfiles
            if file_path.name.startswith("."):
                continue
            if file_path.is_file() and (not self.extensions or any(file_path.suffix == ext for ext in self.extensions)):
                loader = self._predict_loader(file_path)
                data_list.extend(loader.load_data(str(file_path))["data"])
            elif file_path.is_dir():
                logger.info(f"Loading data from directory: {file_path}")
        return data_list

    def _predict_loader(self, file_path: Path) -> BaseLoader:
        try:
            data_type = detect_datatype(str(file_path))
            config = AddConfig()
            return DataFormatter(data_type=data_type, config=config)._get_loader(
                data_type=data_type, config=config.loader, loader=None
            )
        except Exception as e:
            self.errors.append(f"Error processing {file_path}: {e}")
            return TextFileLoader()
