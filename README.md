# Setlist Generation Tool

As a DJ one of the key parts of being a good DJ is having great setlist design and this is typically quite a tedious process as its similar to outlining an essay or planning a project. I wanted to develop a tool to help with my creative process. Using my library of songs stored in an sql lite db I designed song retreival and loading processes. I also utilized Camelot key matching, BPM ranges, and crowd energy profiles in order to optimize and design transitions between songs.

Codebase: Python, Sql Lite, and streamlit

## Key Technical Features

### 1. **Dynamic Graph-Based Pathfinding**
- Uses a DAG (Directed Acyclic Graph) to model harmonic transitions between songs and to ensure no repeats
- Nodes = songs; edges = harmonic compatibility (key & BPM proximity)
- Finds the longest valid path under a time constraint using a dynamic programming approach

### 2. **Energy Curve Segmentation**
- Auto-segments the set into: Build-up, Main, Peak
- I grouped the Camelot keys (1–4 low, 5–8 medium, 9–12 peak) in order to have standardization
- Set duration is split proportionally (e.g., 30% → 50% → 20%)

### 3. **Vibe-Based Scoring System**
- Tracks are scored and filtered based on vibe-specific rules
- Custom logic per vibe (e.g., Frat Party favors pop at 120–135 BPM; Sunset avoids rap/electropop)
- Genre and BPM weighting allows flexibility and personalization

### 4. **Live Streamlit UI**
- Interactive web app with full CRUD support for setlists
- Features include:
  - Add/remove/edit songs
  - Auto-inferred track insertion based on harmonic compatibility
  - Summary stats (avg BPM, genre distribution, total playtime)
  - Export to CSV
  - Load saved setlists

### 5. **Data Management**
- Tracks are imported from `.txt` exports using a robust encoding fallback strategy
- Missing genre fields are imputed via database lookups (mode genre per artist)
- Track uniqueness enforced on (`track_title`, `artist`)

## Future Improvements
As of right now this program has a limited scope of designing a setlist and being a tool to help brainstorm and navigate music, but there are many features I want to add to improve it for the future.
These are some of them:
- Integrating real-time feedback from performance crowd analytics
- Incorporating AI recommendations using collaborative filtering
- Utilizing genre tagging via ML/NLP on metadata
