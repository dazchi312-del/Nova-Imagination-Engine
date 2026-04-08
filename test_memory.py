from core.memory import Memory

def test_save_and_load():
    mem = Memory()
    mem.save("test_key", {"value": "hello"})
    result = mem.load("test_key")
    assert result == {"value": "hello"}, f"FAIL: {result}"
    print("[PASS] save and load")

def test_list_keys():
    mem = Memory()
    mem.save("list_test", {"x": 1})
    keys = mem.list_keys()
    assert "list_test" in keys, f"FAIL: {keys}"
    print("[PASS] list_keys")

def test_delete():
    mem = Memory()
    mem.save("delete_test", {"x": 99})
    mem.delete("delete_test")
    result = mem.load("delete_test")
    assert result == {}, f"FAIL: {result}"
    print("[PASS] delete")

def test_overwrite():
    mem = Memory()
    mem.save("overwrite_test", {"v": 1})
    mem.save("overwrite_test", {"v": 2})
    result = mem.load("overwrite_test")
    assert result == {"v": 2}, f"FAIL: {result}"
    print("[PASS] overwrite via INSERT OR REPLACE")

if __name__ == "__main__":
    test_save_and_load()
    test_list_keys()
    test_delete()
    test_overwrite()
    print("\n[OK] All memory tests passed.")
