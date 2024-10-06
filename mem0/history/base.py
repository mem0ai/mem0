from abc import ABC, abstractmethod

class HistoryDBBase(ABC):
    
    @abstractmethod
    def add_history(
        self,
        memory_id,
        old_memory,
        new_memory,
        event,
        created_at=None,
        updated_at=None,
        is_deleted=0,
    ):
        pass
    
    @abstractmethod
    def get_history(self, memory_id):
        pass

    @abstractmethod
    def reset(self):
        pass