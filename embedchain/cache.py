from typing import Any, Dict, Optional

from gptcache import cache, Config

class Cache():
    def initialize(self):
        cache.init(
            pre_func=self._cache_pre_function,
        )
    
    def _cache_pre_function(self, data: Dict[str, Any], **params: Dict[str, Any]):
        return data["input_query"]
    
    def set_openai_key(self):
        cache.set_openai_key()

cache = Cache()