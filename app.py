import streamlit as st
import pandas as pd
import io

# --- APP CONFIG ---
st.set_page_config(page_title="Jefit Data Optimizer", page_icon="🏋️")
st.title("🏋️ Jefit Workout Optimizer")
st.write("Upload your `jefit.csv` to get an AI-ready compressed text format.")

uploaded_file = st.file_uploader("Choose your Jefit CSV file", type="csv")
months_to_keep = st.sidebar.slider("Months of history to keep", 1, 36, 12)

def process_data(file):
    # Read the file content
    content_raw = file.getvalue().decode("utf-8")
    lines = content_raw.splitlines()

    def get_section(start_marker, end_marker):
        start, end = -1, -1
        for i, line in enumerate(lines):
            if start_marker in line: start = i
            if end_marker in line and i > start:
                end = i
                break
        if start == -1 or end == -1: return None
        section_content = [line.strip() for line in lines[start+1:end] if line.strip()]
        return pd.read_csv(io.StringIO("\n".join(section_content)))

    # 1. Parse Sections
    df_sessions = get_section('### WORKOUT SESSIONS', '### EXERCISE LOGS')
    df_logs = get_section('### EXERCISE LOGS', '### EXERCISE SET LOGS')
    df_sets = get_section('### EXERCISE SET LOGS', '### EXERCISE RECORDS')

    if any(x is None for x in [df_sessions, df_logs, df_sets]):
        st.error("Could not find all required Jefit sections. Ensure you are using the full export.")
        return None

    # 2. Process & Merge
    df_sessions['date'] = pd.to_datetime(df_sessions['starttime'], unit='s')
    df_merged = pd.merge(df_logs, df_sessions, left_on='belongsession', right_on='_id', suffixes=('_log', '_session'))
    df_full = pd.merge(df_sets, df_merged, left_on='exercise_log_id', right_on='_id_log', how='inner')

    # 3. Filter & Sort
    cutoff = pd.Timestamp.now() - pd.DateOffset(months=months_to_keep)
    df_recent = df_full[df_full['date'] >= cutoff].copy()
    df_recent.sort_values(by=['date', 'ename', 'set_index'], inplace=True)

    # 4. Compression
    output_lines = [f"Workout History (Last {months_to_keep} Months)", "Format: Date: Exercise (Weight x Reps, ...)", "-" * 20]

    for date, day_data in df_recent.groupby(df_recent['date'].dt.date):
        day_str_parts = [f"\n{date}:"]
        for exercise, exercise_data in day_data.groupby('ename'):
            sets = []
            for _, row in exercise_data.sort_values('set_index').iterrows():
                w = float(row['weight_lbs']) if not pd.isna(row['weight_lbs']) else 0
                r = int(row['reps']) if not pd.isna(row['reps']) else 0
                sets.append(f"{int(w)}x{r}" if w > 0 else f"{r}r")
            day_str_parts.append(f"{exercise} ({', '.join(sets)})")
        output_lines.append("; ".join(day_str_parts))

    return "\n".join(output_lines)

if uploaded_file:
    result = process_data(uploaded_file)
    if result:
        st.success("Conversion Complete!")
        st.download_button(
            label="Download Optimized Text File",
            data=result,
            file_name="optimized_workout_context.txt",
            mime="text/plain"
        )
        st.text_area("Preview", result, height=300)
