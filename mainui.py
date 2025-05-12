import re
import random
from collections import defaultdict
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
import os
import streamlit as st

# --- Scoring Function ---
def score_track(row, vibe):
    bpm = row['bpm']
    genre = str(row['genre']).strip().lower()
    score = 0

    exclusions = {
        "frat party": ["rock", "afro house"],
        "sunset": [
            "pop", "rap", "rap/hiphop", "hip hop", "hip-hop & rap",
            "electronica", "pitbull", "jersey club", "tiesto"
        ]
    }

    excluded = exclusions.get(vibe.lower(), [])
    if any(g.lower() in genre for g in excluded):
        return 0

    if vibe.lower() == "frat party":
        if "pop" in genre:
            score += 3
        if 120 <= bpm <= 135:
            score += 2
        elif 100 <= bpm < 120 or 136 <= bpm <= 150:
            score += 1

    elif vibe.lower() == "sunset":
        if 95 <= bpm <= 118:
            score += 2
        elif 85 <= bpm < 95 or 119 <= bpm <= 130:
            score += 1

    score += random.uniform(0, 0.3)
    return score

# --- Camelot Logic ---
def parse_key(k):
    match = re.match(r"^(\d{1,2})([AB])$", str(k).strip().upper())
    return (int(match.group(1)), match.group(2)) if match else (None, None)

def get_harmonic_neighbors(key):
    num, mode = parse_key(key)
    if num is None:
        return []
    neighbors = [f"{num}{mode}"]
    neighbors.append(f"{num}{'B' if mode == 'A' else 'A'}")
    neighbors.append(f"{(num % 12) + 1}{mode}")
    neighbors.append(f"{(num - 2) % 12 + 1}{mode}")
    return neighbors

# --- Filter by Key Zones ---
def filter_by_camelot_zone(tracks, key_range):
    result = []
    for t in tracks:
        key = t.get("key", "").strip().upper()
        num, _ = parse_key(key)
        if num and num in key_range:
            result.append(t)
    return result

# --- Load Transitions ---
def load_transitions():
    transition_db_path = os.path.join("..", "transition_manager", "song_transitions.db")
    conn = sqlite3.connect(transition_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT from_artist, from_title, to_artist, to_title FROM transitions")
    rows = cursor.fetchall()
    conn.close()

    transition_pairs = set()
    for from_artist, from_title, to_artist, to_title in rows:
        key = ((from_artist.lower(), from_title.lower()), (to_artist.lower(), to_title.lower()))
        transition_pairs.add(key)
    return transition_pairs

# --- DAG Longest Path Setlist Builder ---
def build_harmonic_graph_setlist(scored_tracks, total_duration_seconds, use_auto_segmentation=True, transitions=None):
    df = [t for t in scored_tracks if t['vibe_score'] > 0 and t['key']]

    if use_auto_segmentation:
        build_time = 1800
        remaining_time = total_duration_seconds - build_time
        main_time = remaining_time * 0.6
        peak_time = remaining_time * 0.4

        segments = [
            (filter_by_camelot_zone(df, range(1, 5)), build_time),
            (filter_by_camelot_zone(df, range(5, 9)), main_time),
            (filter_by_camelot_zone(df, range(9, 13)), peak_time)
        ]
    else:
        segment_duration = total_duration_seconds / 3
        segments = [
            (df, segment_duration),
            (df, segment_duration),
            (df, segment_duration)
        ]

    result = []
    for segment_tracks, segment_time in segments:
        if not segment_tracks:
            continue
        random.shuffle(segment_tracks)
        segment_result = build_segment_graph(segment_tracks, segment_time, transitions)
        result.extend(segment_result)

    return result

# --- Segment Path Logic ---
def build_segment_graph(tracks, total_duration_seconds, transitions=None):
    durations = [estimate_track_duration(t) for t in tracks]
    n = len(tracks)
    graph = [[] for _ in range(n)]

    for i in range(n):
        key1 = tracks[i]['key'].strip().upper()
        bpm1 = tracks[i]['bpm']
        for j in range(n):
            if i == j:
                continue
            key2 = tracks[j]['key'].strip().upper()
            bpm2 = tracks[j]['bpm']
            if key2 in get_harmonic_neighbors(key1) and abs(bpm1 - bpm2) <= 25:
                if transitions:
                    from_pair = (tracks[i]['artist'].lower(), tracks[i]['track_title'].lower())
                    to_pair = (tracks[j]['artist'].lower(), tracks[j]['track_title'].lower())
                    if (from_pair, to_pair) in transitions:
                        graph[i].append(j)
                        continue
                graph[i].append(j)
        random.shuffle(graph[i])

    dp = [(durations[i], [i]) for i in range(n)]
    for i in range(n):
        for j in graph[i]:
            new_time = dp[i][0] + durations[j]
            if new_time <= total_duration_seconds and new_time > dp[j][0]:
                dp[j] = (new_time, dp[i][1] + [j])

    best_path_indices = max(dp, key=lambda x: (x[0] <= total_duration_seconds, x[0], random.random()))[1]
    return [tracks[i] for i in best_path_indices]

# --- Utility Functions ---
def estimate_track_duration(row, ratio=0.7):
    try:
        if 'time' in row and isinstance(row['time'], str) and ':' in row['time']:
            m, s = map(int, row['time'].split(':'))
            total = m * 60 + s
        else:
            total = 210
    except:
        total = 210
    return int(total * ratio)

# --- Streamlit UI ---
st.title("🎶 Smart DJ Setlist Generator")

start_str = st.time_input("Set Start Time", value=datetime.strptime("01:00", "%H:%M"))
end_str = st.time_input("Set End Time", value=datetime.strptime("03:00", "%H:%M"))
vibe = st.selectbox("Select Vibe", ["Frat Party", "Sunset"])
segment_auto = st.checkbox("Auto Segment by Energy Curve", value=True)

if st.button("Generate Setlist"):
    start_time = datetime.combine(datetime.today(), start_str.time())
    end_time = datetime.combine(datetime.today(), end_str.time())
    if end_time <= start_time:
        end_time += timedelta(days=1)

    conn = sqlite3.connect("dj_tracks.db")
    df = pd.read_sql_query("SELECT * FROM tracks", conn)
    df['vibe_score'] = df.apply(lambda row: score_track(row, vibe), axis=1)

    total_duration = (end_time - start_time).total_seconds()
    transitions = load_transitions()
    best_set = build_harmonic_graph_setlist(
        df.to_dict('records'),
        total_duration_seconds=total_duration,
        use_auto_segmentation=segment_auto,
        transitions=transitions
    )

    st.markdown(f"### 🎧 Vibe: {vibe} | 🕒 Duration: {end_time - start_time}")

    for track in best_set:
        st.write(f"{start_time.strftime('%H:%M')} | {track['track_title']} — {track['artist']} | {track['bpm']} BPM | Key {track['key']}")
        start_time += timedelta(seconds=estimate_track_duration(track))
