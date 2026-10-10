import sqlite3
conn = sqlite3.connect("voiceforge.db")
cursor = conn.cursor()
cursor.execute("SELECT name, llm_model FROM agents")
for row in cursor.fetchall():
    print(row)
conn.close()