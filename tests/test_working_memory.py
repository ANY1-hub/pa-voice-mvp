from src.memory.working_memory import WorkingMemory

def test_working_memory_init():
    wm = WorkingMemory("user_123")
    assert wm.user_id == "user_123"
    assert wm.items == []
