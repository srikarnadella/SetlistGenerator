import re
import random
from collections import Counter
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
        "sunset": ["pop", "rap", "rap/hiphop", "hip hop", "hip-hop & rap", "electronica", "pitbull", "jersey club", "tiesto"],
        "kickback": ["rock", "rap", "rap/hiphop", "hip hop", "hip-hop"],
        "rave": ["r&b", "indie pop", "latin pop", "latin music", "hip hop", "hip hop/rap", "pop", "r & b", "demi lovato"],
        "house": ["rap", "hip hop", "hip-hop & rap", "rap/hip-hop", "rock", "pitbull", "jersey club", "demi lovato", "r & b"],
        "poolside": ["rock", "trap", "drill", "metal", "jersey club", "travis scott", "pitbull"]
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
    elif vibe.lower() == "kickback":
        if 120 <= bpm <= 135:
            score += 2
        elif 100 <= bpm < 120 or 136 <= bpm <= 150:
            score += 1
    elif vibe.lower() == "rave":
        if 125 <= bpm <= 140:
            score += 2
        elif 120 <= bpm < 125 or 141 <= bpm <= 150:
            score += 1
        if "techno" in genre or "trance" in genre or "hard" in genre:
            score += 2
    elif vibe.lower() == "house":
        if "house" in genre:
            score += 2
        if 118 <= bpm <= 130:
            score += 2
        elif 110 <= bpm < 118 or 131 <= bpm <= 138:
            score += 1
    elif vibe.lower() == "poolside":
        if "chill" in genre or "tropical" in genre or "deep house" in genre:
            score += 2
        if 100 <= bpm <= 118:
            score += 2
        elif 85 <= bpm < 100 or 119 <= bpm <= 125:
            score += 1

    score += random.uniform(0, 0.3)
    return score

def parse_key(k):
    match = re.match(r"^(\d{1,2})([AB])$", str(k).strip().upper())
    return (int(match.group(1)), match.group(2)) if match else (None, None)

def get_harmonic_neighbors(key):
    num, mode = parse_key(key)
    if num is None:
        return []
    return [
        f"{num}{mode}",
        f"{num}{'B' if mode == 'A' else 'A'}",
        f"{(num % 12) + 1}{mode}",
        f"{(num - 2) % 12 + 1}{mode}"
    ]

def filter_by_camelot_zone(tracks, key_range):
    return [t for t in tracks if parse_key(t.get("key", ""))[0] in key_range]

def load_transitions():
    return set()

def build_harmonic_graph_setlist(tracks, total_secs, use_auto_segmentation=True, transitions=None):
    df = [t for t in tracks if t['vibe_score'] > 0 and t['key']]
    segments = []

    if use_auto_segmentation:
        build, main, peak = 1800, (total_secs - 1800) * 0.6, (total_secs - 1800) * 0.4
        segments = [
            (filter_by_camelot_zone(df, range(1, 5)), build),
            (filter_by_camelot_zone(df, range(5, 9)), main),
            (filter_by_camelot_zone(df, range(9, 13)), peak)
        ]
    else:
        chunk = total_secs / 3
        segments = [(df, chunk)] * 3

    result = []
    for segment_tracks, segment_time in segments:
        random.shuffle(segment_tracks)
        result += build_segment_graph(segment_tracks, segment_time, transitions)

    return result

def build_segment_graph(tracks, total_secs, transitions=None):
    durations = [estimate_track_duration(t) for t in tracks]
    n = len(tracks)
    graph = [[] for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j and abs(tracks[i]['bpm'] - tracks[j]['bpm']) <= 25:
                if tracks[j]['key'] in get_harmonic_neighbors(tracks[i]['key']):
                    graph[i].append(j)
        random.shuffle(graph[i])

    dp = [(durations[i], [i]) for i in range(n)]
    for i in range(n):
        for j in graph[i]:
            new_time = dp[i][0] + durations[j]
            if new_time <= total_secs and new_time > dp[j][0]:
                dp[j] = (new_time, dp[i][1] + [j])

    best_path = max(dp, key=lambda x: (x[0] <= total_secs, x[0], random.random()))[1]
    return [tracks[i] for i in best_path]

def estimate_track_duration(row, ratio=0.7):
    try:
        if isinstance(row.get('time'), str) and ':' in row['time']:
            m, s = map(int, row['time'].split(':'))
            return int((m * 60 + s) * ratio)
    except:
        pass
    return int(210 * ratio)

def summarize_stats(setlist):
    if not setlist: return
    avg_bpm = sum(t['bpm'] for t in setlist) / len(setlist)
    genres = Counter(t['genre'].lower() for t in setlist if t.get('genre'))
    total_time = sum(estimate_track_duration(t) for t in setlist) / 60
    with st.expander("📊 Show Setlist Stats"):
        st.markdown(f"**Average BPM:** {avg_bpm:.1f}")
        st.markdown(f"**Total Playtime:** {total_time:.1f} minutes")
        st.markdown("**Genre Breakdown:**")
        for genre, count in genres.items():
            st.markdown(f"- {genre.title()}: {count}")

def export_setlist_to_csv(setlist, filename="setlist_export.csv"):
    df = pd.DataFrame(setlist)
    st.download_button("📥 Download Setlist as CSV", df.to_csv(index=False), file_name=filename, mime='text/csv')

def save_setlist_to_db(name, setlist):
    if not name or not setlist:
        return
    path = "saved_setlists.csv"
    df = pd.DataFrame([{**t, 'name': name} for t in setlist])
    if os.path.exists(path):
        df.to_csv(path, mode='a', header=False, index=False)
    else:
        df.to_csv(path, index=False)
    st.success(f"✅ Setlist '{name}' saved!")

def load_saved_setlists():
    path = "saved_setlists.csv"
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

# --- Streamlit UI ---
st.title("🎶 Smart DJ Setlist Generator")

setlist_name = st.text_input("📝 Name Your Setlist", value="My New Set")
start_str = st.time_input("Start Time", value=datetime.strptime("01:00", "%H:%M").time())
end_str = st.time_input("End Time", value=datetime.strptime("03:00", "%H:%M").time())
vibe = st.selectbox("Vibe", ["Frat Party", "Sunset", "Kickback", "Rave", "House", "Poolside"])
segment_auto = st.checkbox("Auto Segment", value=True)

conn = sqlite3.connect("dj_tracks.db")
df = pd.read_sql_query("SELECT * FROM tracks", conn)
conn.close()
titles = df['track_title'].dropna().unique().tolist()

if st.button("Generate Setlist"):
    start_time = datetime.combine(datetime.today(), start_str)
    end_time = datetime.combine(datetime.today(), end_str)
    if end_time <= start_time:
        end_time += timedelta(days=1)

    df['vibe_score'] = df.apply(lambda row: score_track(row, vibe), axis=1)
    total_duration = (end_time - start_time).total_seconds()
    st.session_state.edited_set = build_harmonic_graph_setlist(df.to_dict('records'), total_duration_seconds=total_duration, use_auto_segmentation=segment_auto)

if 'edited_set' in st.session_state:
    current_time = datetime.combine(datetime.today(), start_str)
    st.markdown("### 🎧 Final Setlist")
    for i, track in enumerate(st.session_state.edited_set):
        with st.container():
            st.markdown(f"**{current_time.strftime('%H:%M')}** | {track['track_title']} — {track['artist']} | {track['bpm']} BPM | Key {track['key']}")
            current_time += timedelta(seconds=estimate_track_duration(track))
            if st.button("🗑️ Remove", key=f"rm_{i}"):
                st.session_state.edited_set.pop(i)
                st.rerun()

    summarize_stats(st.session_state.edited_set)
    export_setlist_to_csv(st.session_state.edited_set)

    if st.button("💾 Save Setlist"):
        save_setlist_to_db(setlist_name, st.session_state.edited_set)

st.markdown("---")
st.markdown("### ➕ Add Song")
new_title = st.selectbox("Track Title", options=[""] + titles)
row = df[df['track_title'] == new_title].iloc[0] if new_title in df['track_title'].values else None
new_artist = st.text_input("Artist", value=row['artist'] if row is not None else "")
new_bpm = st.number_input("BPM", 60.0, 180.0, value=float(row['bpm']) if row is not None else 120.0)
new_key = st.text_input("Camelot Key", value=row['key'] if row is not None else "")
new_genre = st.text_input("Genre", value=row['genre'] if row is not None else "")

if st.button("Add to Setlist"):
    if 'edited_set' not in st.session_state:
        st.session_state.edited_set = []

    new_track = {
        "track_title": new_title,
        "artist": new_artist,
        "bpm": new_bpm,
        "key": new_key,
        "genre": new_genre,
        "vibe_score": 2
    }

    inserted = False
    for i in range(len(st.session_state.edited_set)):
        if new_key.upper() in get_harmonic_neighbors(st.session_state.edited_set[i]['key']):
            st.session_state.edited_set.insert(i + 1, new_track)
            inserted = True
            break
    if not inserted:
        st.session_state.edited_set.append(new_track)

    st.success(f"✅ Added '{new_title}'")
    st.rerun()

st.markdown("---")
st.markdown("### 📁 Load Saved Setlist")
saved_df = load_saved_setlists()
if not saved_df.empty:
    name = st.selectbox("Choose a Setlist", [""] + saved_df['name'].unique().tolist())
    if name:
        st.session_state.edited_set = saved_df[saved_df['name'] == name].to_dict('records')
        st.rerun()
