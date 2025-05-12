import os
import sqlite3
import pandas as pd

db_path = "dj_tracks.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

#if the table doesn't exist it gets created
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tracks (
        track_title TEXT,
        artist TEXT,
        bpm REAL,
        key TEXT,
        genre TEXT,
        UNIQUE(track_title, artist)
    )
''')
conn.commit()


def read_file_with_encoding_fallback(filepath):
    encodings = ['utf-8', 'utf-16', 'ISO-8859-1', 'windows-1252']
    for enc in encodings:
        try:
            return pd.read_csv(filepath, sep='\t', encoding=enc)
        except Exception:
            continue
    raise ValueError(f"Failed to read file with any known encoding: {filepath}")

#if null it finds the most frequent genre for a given artist in the DB
def get_artist_most_common_genre(artist):
    cursor.execute('''
        SELECT genre FROM tracks
        WHERE artist = ? AND genre IS NOT NULL AND genre != ''
    ''', (artist,))
    genres = [row[0] for row in cursor.fetchall()]
    if not genres:
        return None
    return pd.Series(genres).mode()[0]  # most frequent genre

def load_txt_files(folder="data"):
    for filename in os.listdir(folder):
        if filename.endswith(".txt"):
            filepath = os.path.join(folder, filename)
            try:
                df = read_file_with_encoding_fallback(filepath)
                subset = df[['Track Title', 'Artist', 'BPM', 'Key', 'Genre']]
                for _, row in subset.iterrows():
                    genre = row['Genre']
                    if pd.isna(genre) or str(genre).strip() == "":
                        inferred_genre = get_artist_most_common_genre(row['Artist'])
                        genre = inferred_genre if inferred_genre else None
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO tracks (track_title, artist, bpm, key, genre)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (row['Track Title'], row['Artist'], row['BPM'], row['Key'], genre))
                    except Exception as e:
                        print(f"Insert error in {filename}, row {row}: {e}")
            except Exception as e:
                print(f"Failed to read {filename}: {e}")
    conn.commit()

load_txt_files("data")
conn.close()
