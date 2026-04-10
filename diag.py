import psutil
from core.config import load_config
from core.reflector import Reflector
from core.identity import get_identity
from core import tools as tm

m = psutil.virtual_memory()
print("RAM:", round(m.total/1e9,1), "GB")
c = load_config()
print("Config OK -> model:", c["lm_studio"]["model"])
ident = get_identity()
print("Identity OK ->", ident.get("name","NOT SET"))
real_tools = ["list_directory","list_files","read_file","run_code","run_shell","write_file"]
found = [x for x in real_tools if hasattr(tm, x)]
print("Tools loaded ->", len(found), "tools:", found)
r = Reflector()
print("Reflector OK -> REPETITION_THRESHOLD:", r.REPETITION_THRESHOLD)
print("ALL SYSTEMS GO")
