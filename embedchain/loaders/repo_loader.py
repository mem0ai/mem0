import logging
import os
import shutil
import subprocess
import tempfile
import urllib.parse

try:
    from repo_loader import repo_loader
except ImportError:
    raise ImportError(
        "Repo Loader requires extra dependencies. Install with `pip install repo-loader` or `pip install embedchain[community]`"  # noqa #E501
    ) from None

from embedchain.loaders.base_loader import BaseLoader


class RepoLoader(BaseLoader):
    def load_data(self, content):
        """Load data from a git repository."""

        # Check if content is a local directory
        if os.path.isdir(content):
            directory = os.path.abspath(content)
            logging.debug(f"Loading repository from local directory: {directory}")
            origin = directory
            is_local = True
        else:
            # Check if content is a valid URL
            try:
                result = urllib.parse.urlparse(content)
                if all([result.scheme, result.netloc]):
                    # If content is a valid URL, clone the repository into a temporary directory
                    temp_dir = tempfile.mkdtemp()
                    try:
                        subprocess.run(["git", "clone", content, temp_dir], check=True)
                        directory = temp_dir
                        logging.debug(f"Cloned repository from {content} to temporary directory {temp_dir}")
                        origin = content
                    except subprocess.CalledProcessError:
                        shutil.rmtree(temp_dir)  # clean up
                        raise ValueError(f"Failed to clone repository from URL: {content}")
                    is_local = False
                else:
                    raise ValueError("The content must be a valid local directory or a valid URL")
            except ValueError as ve:
                logging.error(str(ve))
                raise

        # This creates a temporary file and opens it for writing
        temp_file = tempfile.NamedTemporaryFile(delete=False)

        try:
            outfile = temp_file.name
            logging.debug(f"repository temp file located at: {temp_file.name}")

            repo_loader.load(directory, out_path=outfile, preamble="", quiet=True, progress=True)

            # Ensure everything is written
            temp_file.flush()

            # Seek back to the beginning of the file if you want to read it
            temp_file.seek(0)

            filecontent = temp_file.read().decode()

            # Files is read again with the readlines method, to count the lines.
            # In some cases, this might be too expensive just for logging.
            temp_file.seek(0)
            lines = temp_file.readlines()

            individual_file_content = filecontent.split("----!@#$----")
            logging.info(f"repository read, {len(individual_file_content)} files, {len(lines)} lines")

            # TODO: Repo name as metadata, whether it's remote or local.
            meta_data = {
                "url": f"repo-{origin}" if is_local else content,
            }

            output = [{"content": file, "meta_data": meta_data} for file in individual_file_content]

        finally:
            # Make sure you close the file when you're done with it
            temp_file.close()

            # If the directory was a temporary one, remove it
            try:
                if temp_dir and directory == temp_dir:
                    shutil.rmtree(temp_dir)
            except UnboundLocalError:
                # Make sure cleanup doesn't fail if no temp_dir was created.
                pass

        return output
