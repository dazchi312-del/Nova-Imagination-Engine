from core.memory import Memory

mem = Memory()

mem.save("user_name", {"name": "David"})
print(mem.load("user_name"))

mem.save("goal", {"goal": "Build Nova"})
print(mem.load("goal"))

print(mem.list_keys())