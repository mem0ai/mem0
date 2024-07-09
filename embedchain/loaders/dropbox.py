import hashlib
import os

from dropbox.files import FileMetadata

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.loaders.directory_loader import DirectoryLoader


@register_deserializable
class DropboxLoader(BaseLoader):
    def __init__(self):
        access_token = os.environ.get("DROPBOX_ACCESS_TOKEN")
        if not access_token:
            raise ValueError("Please set the `DROPBOX_ACCESS_TOKEN` environment variable.")
        try:
            from dropbox import Dropbox, exceptions
        except ImportError:
            raise ImportError("Dropbox requires extra dependencies. Install with `pip install dropbox==11.36.2`")

        try:
            dbx = Dropbox(access_token)
            dbx.users_get_current_account()
            self.dbx = dbx
        except exceptions.AuthError as ex:
            raise ValueError("Invalid Dropbox access token. Please verify your token and try again.") from ex

    def _download_folder(self, path: str, local_root: str) -> list[FileMetadata]:
        """Download a folder from Dropbox and save it preserving the directory structure."""
        entries = self.dbx.files_list_folder(path).entries
        for entry in entries:
            local_path = os.path.join(local_root, entry.name)
            if isinstance(entry, FileMetadata):
                self.dbx.files_download_to_file(local_path, f"{path}/{entry.name}")
            else:
                os.makedirs(local_path, exist_ok=True)
                self._download_folder(f"{path}/{entry.name}", local_path)
        return entries

    def _generate_dir_id_from_all_paths(self, path: str) -> str:
        """Generate a unique ID for a directory based on all of its paths."""
        entries = self.dbx.files_list_folder(path).entries
        paths = [f"{path}/{entry.name}" for entry in entries]
        return hashlib.sha256("".join(paths).encode()).hexdigest()

    def load_data(self, path: str):
        """Load data from a Dropbox URL, preserving the folder structure."""
        root_dir = f"dropbox_{self._generate_dir_id_from_all_paths(path)}"
        os.makedirs(root_dir, exist_ok=True)

        for entry in self.dbx.files_list_folder(path).entries:
            local_path = os.path.join(root_dir, entry.name)
            if isinstance(entry, FileMetadata):
                self.dbx.files_download_to_file(local_path, f"{path}/{entry.name}")
            else:
                os.makedirs(local_path, exist_ok=True)
                self._download_folder(f"{path}/{entry.name}", local_path)

        dir_loader = DirectoryLoader()
        data = dir_loader.load_data(root_dir)["data"]

        # Clean up
        self._clean_directory(root_dir)

        return {
            "doc_id": hashlib.sha256(path.encode()).hexdigest(),
            "data": data,
        }

    def _clean_directory(self, dir_path):
        """Recursively delete a directory and its contents."""
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                self._clean_directory(item_path)
            else:
                os.remove(item_path)
        os.rmdir(dir_path)
