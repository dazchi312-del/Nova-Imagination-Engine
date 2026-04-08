import datetime
from datetime import datetime as dt

def get_current_time():
    now = dt.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

print(get_current_time())