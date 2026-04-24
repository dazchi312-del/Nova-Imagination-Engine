import sqlite3
import time

conn = sqlite3.connect('nova.db')
conn.row_factory = sqlite3.Row

print('-- Stored Results --')
rows = conn.execute(
    'SELECT r.id, t.name, r.ran_at, substr(r.output, 1, 200) as preview'
    ' FROM results r JOIN tasks t ON r.task_id = t.id'
    ' ORDER BY r.ran_at DESC LIMIT 6'
).fetchall()

if not rows:
    print('  (no results yet)')
else:
    for r in rows:
        ts = time.strftime('%H:%M:%S', time.localtime(r['ran_at']))
        print('  [' + ts + '] ' + r['name'])
        print('    ' + str(r['preview']))
        print()

print('-- Recent Events --')
events = conn.execute(
    'SELECT ts, source, event, detail FROM events ORDER BY ts DESC LIMIT 8'
).fetchall()