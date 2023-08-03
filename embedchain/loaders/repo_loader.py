import tempfile
import logging

from repo_loader import repo_loader

from embedchain.loaders.base_loader import BaseLoader


class RepoLoader(BaseLoader):
    def load_data(self, content):
        """Load data from a git repository."""

        # This creates a temporary file and opens it for writing
        temp_file = tempfile.NamedTemporaryFile(delete=False)

        try:
            outfile = temp_file.name
            logging.debug(f"repository temp file located at: {temp_file.name}")

            repo_loader.load(content, out_path=outfile, preamble="", quiet=True, progress=True)

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
                "url": content,
            }

            output = [{"content": file, "meta_data": meta_data} for file in individual_file_content]

        finally:
            # Make sure you close the file when you're done with it
            temp_file.close()

        return output
