from embedchain.chunkers.base_chunker import BaseChunker

class SlackChunker(BaseChunker):
    
    def __init__(self):
        text_splitter = lambda x: x
        super().__init__(text_splitter)
    
    def get_chunks(self, content):
        return [content]
