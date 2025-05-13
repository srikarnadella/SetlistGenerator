import re
import random
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
import os
import streamlit as st

def score_track(row, vibe):
    bpm = row['bpm']
    genre = str(row['genre']).strip().lower()
    score = 0

    #Inclusions were more difficult to isolate so incorpoated exclusions
    exclusions = {
        "frat party": ["rock", "afro house"],
        "sunset": [
            "pop", "rap", "rap/hiphop", "hip hop", "hip-hop & rap",
            "electronica", "pitbull", "jersey club", "tiesto"
        ],
        "kickback": ["rock", "rap", "rap/hiphop", "hip hop", "hip-hop"],
        "rave": [
            "r&b", "indie pop", "latin pop", "latin music", "hip hop", "hip hop/rap", "pop", 
            "r & b", "demi lovato"
        ],
        "house": [
            "rap", "hip hop", "hip-hop & rap", "rap/hip-hop", "rock", "pitbull", 
            "jersey club",  "demi lovato", "r & b"
        ],
        "poolside": [
            "rock", "trap", "drill", "metal","jersey club", "travis scott", "pitbull",
        ]
    }


    excluded = exclusions.get(vibe.lower(), [])
    #drafted a scoring tool in order to priortize the songs
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
    elif vibe.lower() == "kick back":
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

#tool to key match
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

def filter_by_camelot_zone(tracks, key_range):
    result = []
    for t in tracks:
        key = t.get("key", "").strip().upper()
        num, _ = parse_key(key)
        if num and num in key_range:
            result.append(t)
    return result


def load_transitions():
    return set()


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

def summarize_stats(setlist):
    if not setlist:
        return
    avg_bpm = sum(t['bpm'] for t in setlist) / len(setlist)
    genres = Counter(t['genre'].lower() for t in setlist if t.get('genre'))
    total_time = sum(estimate_track_duration(t) for t in setlist) / 60
    st.markdown(f"**Average BPM:** {avg_bpm:.1f}")
    st.markdown(f"**Total Playtime:** {total_time:.1f} minutes")
    st.markdown("**Genre Breakdown:**")
    for genre, count in genres.items():
        st.markdown(f"- {genre.title()}: {count} song(s)")

def export_setlist_to_csv(setlist, filename="setlist_export.csv"):
    df = pd.DataFrame(setlist)
    df.to_csv(filename, index=False)
    st.download_button("📥 Download Setlist", data=df.to_csv(index=False), file_name=filename, mime='text/csv')


def save_setlist_to_db(name, setlist):
    if not name or not setlist:
        return
    path = "saved_setlists.csv"
    rows = []
    for track in setlist:
        track_copy = track.copy()
        track_copy['name'] = name
        rows.append(track_copy)
    df = pd.DataFrame(rows)
    if os.path.exists(path):
        df.to_csv(path, mode='a', header=False, index=False)
    else:
        df.to_csv(path, index=False)
    st.success(f"Setlist '{name}' saved!")

def load_saved_setlists():
    path = "saved_setlists.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

st.title("Smart DJ Setlist Generator")

start_str = st.time_input("Set Start Time", value=datetime.strptime("01:00", "%H:%M").time())
end_str = st.time_input("Set End Time", value=datetime.strptime("03:00", "%H:%M").time())
vibe = st.selectbox("Select Vibe", [ "Sunset", "Kick back", "Rave", "House", "Poolside", "Frat Party"])
segment_auto = st.checkbox("Auto Segment by Energy Curve", value=True)

conn = sqlite3.connect("dj_tracks.db")
df = pd.read_sql_query("SELECT * FROM tracks", conn)
existing_titles = df['track_title'].dropna().unique().tolist()

if st.button("Generate Setlist"):
    start_time = datetime.combine(datetime.today(), start_str)
    end_time = datetime.combine(datetime.today(), end_str)
    if end_time <= start_time:
        end_time += timedelta(days=1)

    df['vibe_score'] = df.apply(lambda row: score_track(row, vibe), axis=1)
    total_duration = (end_time - start_time).total_seconds()
    transitions = load_transitions()
    best_set = build_harmonic_graph_setlist(df.to_dict('records'), total_duration_seconds=total_duration, use_auto_segmentation=segment_auto, transitions=transitions)

    st.session_state.edited_set = best_set

st.markdown("###  Final Edited Setlist")
if 'edited_set' in st.session_state:
    current_time = datetime.combine(datetime.today(), start_str)
    for i, track in enumerate(st.session_state.edited_set):
        with st.container():
            st.markdown(f"**{current_time.strftime('%H:%M')}** | {track['track_title']} — {track['artist']} | {track['bpm']} BPM | Key {track['key']}", help=f"Genre: {track.get('genre', '')}")
            current_time += timedelta(seconds=estimate_track_duration(track))
            remove = st.button(f"Remove", key=f"remove_{i}")
            if remove:
                st.session_state.edited_set.pop(i)
                st.rerun()

    summarize_stats(st.session_state.edited_set)
    st.markdown("---")
    name_to_save = st.text_input("Name this Setlist")
    if st.button(" Save Setlist"):
        save_setlist_to_db(name_to_save, st.session_state.edited_set)

st.markdown("---")
st.markdown("###  Add a New Song")
new_title = st.selectbox("Track Title", options=[""] + existing_titles)

matched_row = df[df['track_title'] == new_title].iloc[0] if new_title in df['track_title'].values else None
new_artist = st.text_input("Artist", value=matched_row['artist'] if matched_row is not None else "")
new_bpm = st.number_input("BPM", min_value=60.0, max_value=180.0, value=float(matched_row['bpm']) if matched_row is not None else 120.0)
new_key = st.text_input("Camelot Key (e.g. 6A, 5B)", value=matched_row['key'] if matched_row is not None else "")
new_genre = st.text_input("Genre", value=matched_row['genre'] if matched_row is not None else "")

if new_title and new_title not in existing_titles:
    st.warning("⚠️ This title is not in our records.")

if st.button("Add Song to Setlist"):
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

    # Try to insert after best harmonic fit
    inserted = False
    for i in range(len(st.session_state.edited_set)):
        curr_key = st.session_state.edited_set[i]['key'].strip().upper()
        if new_key.strip().upper() in get_harmonic_neighbors(curr_key):
            st.session_state.edited_set.insert(i + 1, new_track)
            inserted = True
            break

    if not inserted:
        st.session_state.edited_set.append(new_track)

    st.success(f" '{new_title}' added to setlist!")
    st.rerun()

st.markdown("---")
st.markdown("### Load Saved Setlist")
saved_df = load_saved_setlists()
if not saved_df.empty:
    names = saved_df['name'].unique().tolist()
    chosen_name = st.selectbox("Choose Saved Setlist", options=[""] + names)
    if chosen_name:
        loaded = saved_df[saved_df['name'] == chosen_name].to_dict('records')
        st.session_state.edited_set = loaded
        st.rerun()
