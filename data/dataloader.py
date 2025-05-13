import os
import sqlite3
import pandas as pd

# Correct path to DB in parent folder
db_path = os.path.join("..", "dj_tracks.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create table if it doesn't exist
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

# Try reading TXT with different encodings
def read_file_with_encoding_fallback(filepath):
    encodings = ['utf-8', 'utf-16', 'ISO-8859-1', 'windows-1252']
    for enc in encodings:
        try:
            return pd.read_csv(filepath, sep='\t', encoding=enc)
        except Exception:
            continue
    raise ValueError(f"Failed to read file with any known encoding: {filepath}")

# Infer genre from artist history
def get_artist_most_common_genre(artist):
    cursor.execute('''
        SELECT genre FROM tracks
        WHERE artist = ? AND genre IS NOT NULL AND genre != ''
    ''', (artist,))
    genres = [row[0] for row in cursor.fetchall()]
    if not genres:
        return None
    return pd.Series(genres).mode()[0]

# Load all .txt files in current folder
def load_txt_files(folder="."):
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
                            INSERT OR REPLACE INTO tracks (track_title, artist, bpm, key, genre)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            row['Track Title'], 
                            row['Artist'], 
                            row['BPM'], 
                            row['Key'], 
                            genre
                        ))
                    except Exception as e:
                        print(f"Insert error in {filename}, row {row}: {e}")
            except Exception as e:
                print(f"Failed to read {filename}: {e}")
    conn.commit()

# Run the loader
load_txt_files(".")
conn.close()
