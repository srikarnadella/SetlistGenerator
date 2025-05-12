import re
from collections import defaultdict
from datetime import datetime, timedelta
import sqlite3
import pandas as pd

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

# --- DAG Longest Path Setlist Builder ---
def build_harmonic_graph_setlist(scored_tracks, total_duration_seconds, use_auto_segmentation=True):
    df = [t for t in scored_tracks if t['vibe_score'] > 0 and t['key']]

    if use_auto_segmentation:
        build_time = 1800  # 30 minutes for build-up
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
        segment_result = build_segment_graph(segment_tracks, segment_time)
        result.extend(segment_result)

    return result

# --- Segment Path Logic ---
def build_segment_graph(tracks, total_duration_seconds):
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

    dp = [(durations[i], [i]) for i in range(n)]
    for i in range(n):
        for j in graph[i]:
            new_time = dp[i][0] + durations[j]
            if new_time <= total_duration_seconds and new_time > dp[j][0]:
                dp[j] = (new_time, dp[i][1] + [j])

    best_path_indices = max(dp, key=lambda x: (x[0] <= total_duration_seconds, x[0]))[1]
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

def print_timestamped_setlist(start_time, setlist):
    current = start_time
    for track in setlist:
        print(f"{current.strftime('%H:%M')} | {track['track_title']} — {track['artist']} | {track['bpm']} BPM | Key {track['key']}")
        duration = estimate_track_duration(track)
        current += timedelta(seconds=duration)
def export_setlist_to_csv(start_time, setlist, filename="exported_setlist.csv"):
    rows = []
    current = start_time
    for track in setlist:
        rows.append({
            "Time": current.strftime('%H:%M'),
            "Title": track['track_title'],
            "Artist": track['artist'],
            "BPM": track['bpm'],
            "Key": track['key']
        })
        current += timedelta(seconds=estimate_track_duration(track))
    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False)
    print(f"\n📁 Setlist exported to {filename}")

# --- Main Function ---
def main():
    conn = sqlite3.connect("dj_tracks.db")
    df = pd.read_sql_query("SELECT * FROM tracks", conn)

    start_str = input("Enter set start time (HH:MM): ")
    end_str = input("Enter set end time (HH:MM): ")
    vibe = input("Enter vibe (e.g. Frat Party, Sunset): ").strip()
    segmentation_mode = input("Segment manually? (y/n): ").strip().lower()
    use_auto = segmentation_mode != 'y'

    start_time = datetime.strptime(start_str, "%H:%M")
    end_time = datetime.strptime(end_str, "%H:%M")
    if end_time <= start_time:
        end_time += timedelta(days=1)

    total_duration = (end_time - start_time).total_seconds()
    df['vibe_score'] = df.apply(lambda row: score_track(row, vibe), axis=1)
    best_set = build_harmonic_graph_setlist(df.to_dict('records'), total_duration_seconds=total_duration, use_auto_segmentation=use_auto)

    print(f"\n🕒 Set duration: {end_time - start_time}")
    print(f"🎧 Vibe selected: {vibe}\n")
    print("🎶 Generated Setlist:\n" + "-" * 50)
    print_timestamped_setlist(start_time, best_set)
    export = input("Export setlist to CSV? (y/n): ").strip().lower()
    if export == 'y':
        export_setlist_to_csv(start_time, best_set)


if __name__ == "__main__":
    main()
