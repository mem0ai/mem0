from typing import Optional

from langchain.text_splitter import Language, RecursiveCharacterTextSplitter
from whats_that_code.election import guess_language_all_methods
import logging

from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config.AddConfig import ChunkerConfig


class RepoChunker(BaseChunker):
    """Chunker for repositories."""

    def __init__(self, config: Optional[ChunkerConfig] = None):
        if config is None:
            config = ChunkerConfig(chunk_size=50, chunk_overlap=0, length_function=len)
        config._use_dynamic_chunker = True
        
        super().__init__(None, config)

    def _set_dynamic_text_splitter(self, content, metadata):
        filename = metadata.get('filename')

        detected_language = RepoChunker._get_detected_language(filename, content)

        if detected_language:
            self.text_splitter = RecursiveCharacterTextSplitter.from_language(
                language=detected_language,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                length_function=self.config.length_function,
            )
        else:
            # Fallback if filetype could not be detected.
            self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=self.config.length_function,
        )

    @staticmethod
    def _get_detected_language(filename, code) -> Language:
        detected = guess_language_all_methods(code, file_name=filename)
        logging.debug(f"Detected `{filename}` as `{detected}`")

        # Rewrites
        if detected == "javascript":
            detected = Language.JS

        if detected not in [language.value for language in Language]:
            logging.debug(f"Detected language `{detected}` is not a compatibe language. Falling back to plaintext text splitter.")
            return None
        

        return detected
