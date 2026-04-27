import pytest
from pathlib import Path
from nova.core.memory import remember, recall, set_store, _get_store
from nova.core.episodic import EpisodicStore

@pytest.fixture(autouse=True)
def memory_isolation(tmp_path):
    """
    Every test gets a clean, temporary database.
    This protects your real Nova data from test drift.
    """
    test_db_path = tmp_path / "test_memory.db"
    test_store = EpisodicStore(test_db_path)
    
    # Injection: Tell the facade to use this test store
    set_store(test_store)
    
    yield
    
    # Teardown: Reset to None so the next test starts with a clean slate
    set_store(None)

def test_lazy_initialization_flow():
    """PROVE: The 'Lazy Hit'—it inits only when needed."""
    # Force the state back to None
    set_store(None)
    
    # Access the internal variable to prove it's dormant
    import nova.core.memory as mem
    assert mem._store is None
    
    # First functional call should trigger the 'Hit'
    remember(kind="test", content="Activating the substrate")
    assert mem._store is not None

def test_remember_and_recall_roundtrip():
    """PROVE: Content integrity across the facade."""
    content = "The identity layer must be built on verifiable truth."
    ep = remember(kind="philosophy", content=content)
    
    # Did we get a valid SHA-256 hash back?
    assert len(ep.hash) == 64
    
    # Can we get it back using the hash?
    retrieved = recall(ep.hash)
    assert retrieved is not None
    assert retrieved.content == content
    assert retrieved.hash == ep.hash

def test_memory_idempotency_at_facade():
    """PROVE: Duplicate experiences don't double-count."""
    remember(kind="event", content="Calibration")
    remember(kind="event", content="Calibration")
    
    # The internal store should only have 1 record
    assert _get_store().count() == 1

