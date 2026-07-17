import pytest

from src.security.exceptions import MemoryWritePolicyViolation
from src.security.memory_policy import can_write_to_memory


def test_can_write_high_importance():
    fact = {"content": "User likes coffee without milk"}
    assert can_write_to_memory(fact, importance_score=0.8, source="user") is True


def test_reject_low_importance():
    fact = {"content": "Random small detail"}
    assert can_write_to_memory(fact, importance_score=0.2) is False


def test_reject_unknown_source():
    fact = {"content": "Something"}
    with pytest.raises(MemoryWritePolicyViolation):
        can_write_to_memory(fact, importance_score=0.7, source="hacker")
