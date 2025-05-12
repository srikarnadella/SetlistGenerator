import sqlite3

conn = sqlite3.connect("dj_tracks.db")
cursor = conn.cursor()

cursor.execute("SELECT DISTINCT genre FROM tracks")
genres = cursor.fetchall()

print("🎵 Genres in your database:")
for g in genres:
    print("-", g[0])
