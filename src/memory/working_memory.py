# Working Memory - kurzer Kontext, TTL, Importance
# TODO Phase 1: Implementierung

class WorkingMemory:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.items = []  # später In-Memory oder Redis/Mongo

    def add(self, content: str, importance: float = 0.5):
        pass

    def retrieve(self, query: str = None):
        pass
