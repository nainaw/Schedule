import os
import json
import base64
import requests
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta, date

st.set_page_config(page_title="Church Schedule Generator", layout="wide")

st.title("⛪ Church Schedule Planning Generator")
st.markdown("Upload your datasets (or use default repository files), customize group rules and Sabbath dates, and automatically generate the fair-rotation planning sheet.")

# --- HELPER: GITHUB AUTO-COMMIT (ROBUST FOR NEW/EXISTING FILES) ---
def update_github_csv(new_rows_df, file_path="Planning.csv"):
    """Appends new schedule rows to Planning.csv and commits directly to GitHub (creates file if missing)."""
    if "GITHUB_TOKEN" not in st.secrets or "REPO_NAME" not in st.secrets:
        return False, "GitHub credentials not found in Streamlit Secrets."

    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["REPO_NAME"]
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. Try fetching current file content and sha from GitHub
    res = requests.get(url, headers=headers)
    
    sha = None
    current_df = pd.DataFrame(columns=["Date", "Task", "AssignedMember"])
    
    if res.status_code == 200:
        file_data = res.json()
        sha = file_data["sha"]
        current_content = base64.b64decode(file_data["content"]).decode("utf-8")
        current_df = pd.read_csv(pd.io.common.StringIO(current_content))
    elif res.status_code == 404:
        # File doesn't exist yet, we will create it fresh
        pass
    else:
        return False, f"Failed to check {file_path} on GitHub: {res.text}"

    # 2. Append new generated rows
    updated_df = pd.concat([current_df, new_rows_df], ignore_index=True)
    updated_csv_str = updated_df.to_csv(index=False)

    # 3. Commit updated CSV back to GitHub
    encoded_content = base64.b64encode(updated_csv_str.encode("utf-8")).decode("utf-8")
    payload = {
        "message": "Auto-update Planning.csv from Streamlit Schedule Generator",
        "content": encoded_content,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    put_res = requests.put(url, headers=headers, data=json.dumps(payload))
    if put_res.status_code in [200, 201]:
        return True, "Successfully updated Planning.csv in GitHub!"
    else:
        return False, f"Failed to commit to GitHub: {put_res.text}"


# --- SIDEBAR: FILE UPLOADS WITH DEFAULT FALLBACK ---
st.sidebar.header("1. Upload CSV Files (Optional)")
uploaded_members = st.sidebar.file_uploader("Members.csv", type=["csv"])
uploaded_competencies = st.sidebar.file_uploader("Competencies.csv", type=["csv"])
uploaded_tasks = st.sidebar.file_uploader("Tasks.csv", type=["csv"])
uploaded_planning = st.sidebar.file_uploader("Planning.csv (History for Rotation)", type=["csv"])

def load_data(uploaded_file, default_filename):
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    elif os.path.exists(default_filename):
        return pd.read_csv(default_filename)
    return None

members_df = load_data(uploaded_members, "Members.csv")
competencies_df = load_data(uploaded_competencies, "Competencies.csv")
tasks_df = load_data(uploaded_tasks, "Tasks.csv")
planning_df = load_data(uploaded_planning, "Planning.csv")

if members_df is not None and competencies_df is not None and tasks_df is not None:
    task_id_to_name = dict(zip(tasks_df['id'].astype(str), tasks_df['name'].astype(str)))
    task_names = tasks_df['name'].dropna().astype(str).tolist()

    # --- SIDEBAR: SETTINGS ---
    st.sidebar.header("2. Planning Period & Settings")
    start_date = st.sidebar.date_input("Start Date", value=date.today(), key="start_date_input")
    num_sabbaths = st.sidebar.slider("Number of Sabbaths to Generate", min_value=1, max_value=10, value=2, key="num_sabbaths_slider")

    st.sidebar.header("3. Special Rules Configuration")
    elder_sabbath_choice = st.sidebar.selectbox(
        "Reserve CUTL for Elder on which Sabbath of Trimester Start Months (Jan, Apr, Jul, Oct)?",
        options=[1, 2, 3, 4, 5],
        index=1,
        key="elder_sabbath_selectbox"
    )

    st.sidebar.header("4. Group Rule Configuration")
    default_ss = [t for t in ["SSM", "SST", "SS5"] if t in task_names]
    default_cu = [t for t in ["SSM", "SST", "SS5", "CUM", "CUVK", "CUVP", "CUFN", "CUTA", "CUTL"] if t in task_names]

    sabbath_1_group = st.sidebar.text_input("1st Sabbath Group", value="Tanora Zokiny", key="s1_grp")
    sabbath_1_tasks = st.sidebar.multiselect("1st Sabbath Group Tasks", options=task_names, default=default_ss, key="s1_tsk")

    sabbath_2_group = st.sidebar.text_input("2nd Sabbath Group", value="Zatovo", key="s2_grp")
    sabbath_2_tasks = st.sidebar.multiselect("2nd Sabbath Group Tasks", options=task_names, default=default_ss, key="s2_tsk")

    sabbath_3_group = st.sidebar.text_input("3rd Sabbath Group", value="Lehibe I", key="s3_grp")
    sabbath_3_tasks = st.sidebar.multiselect("3rd Sabbath Group Tasks", options=task_names, default=default_ss, key="s3_tsk")

    sabbath_4_group = st.sidebar.text_input("4th Sabbath Group", value="Lehibe II", key="s4_grp")
    sabbath_4_tasks = st.sidebar.multiselect("4th Sabbath Group Tasks", options=task_names, default=default_ss, key="s4_tsk")

    sabbath_5_group = st.sidebar.text_input("5th Sabbath Group", value="MINENF", key="s5_grp")
    sabbath_5_tasks = st.sidebar.multiselect("5th Sabbath Group Tasks", options=task_names, default=default_cu, key="s5_tsk")

    # --- CALCULATE SABBATH DATES ---
    def get_next_saturdays(start_dt, count):
        if isinstance(start_dt, datetime):
            start_dt = start_dt.date()
        cur = start_dt + timedelta(days=(5 - start_dt.weekday()) % 7)
        saturdays = []
        while len(saturdays) < count:
            saturdays.append(cur)
            cur += timedelta(days=7)
        return saturdays

    all_saturdays = get_next_saturdays(start_date, num_sabbaths)

    st.subheader("📅 Sabbath Calendar & Skipped Dates")
    selected_saturdays = []
    col1, col2 = st.columns(2)
    for i, sat in enumerate(all_saturdays):
        col = col1 if i % 2 == 0 else col2
        first_day_of_month = date(sat.year, sat.month, 1)
        first_sat = first_day_of_month + timedelta(days=(5 - first_day_of_month.weekday()) % 7)
        sabbath_idx = ((sat - first_sat).days // 7) + 1

        label = f"{sat.strftime('%d/%m/%Y')} (Sabbath {sabbath_idx} of {sat.strftime('%B')})"
        if col.checkbox(label, value=True, key=f"sat_cb_{sat}"):
            selected_saturdays.append((sat, sabbath_idx))

    # --- HISTORICAL TRACKING & ROTATION INITIALIZATION ---
    available_members = members_df[members_df['available'] == True]['name'].tolist()
    last_performed_date = {m: {} for m in available_members}
    last_sabbath_assigned_members = set()

    if planning_df is not None and not planning_df.empty:
        planning_df['parsed_date'] = pd.to_datetime(planning_df['Date'], format='%d/%m/%Y', errors='coerce')
        if not planning_df['parsed_date'].isna().all():
            max_date = planning_df['parsed_date'].max()
            last_sabbath_rows = planning_df[planning_df['parsed_date'] == max_date]
            last_sabbath_assigned_members = set(last_sabbath_rows['AssignedMember'].dropna().astype(str).str.strip())

        for _, row in planning_df.iterrows():
            m_name = str(row.get('AssignedMember', '')).strip()
            t_val = str(row.get('Task', '')).strip()
            t_name = task_id_to_name.get(t_val, t_val)
            p_date_raw = row.get('parsed_date')
            
            if m_name in last_performed_date and pd.notna(p_date_raw):
                p_date = pd.to_datetime(p_date_raw).date()
                current_latest = last_performed_date[m_name].get(t_name)
                if current_latest is None or p_date > current_latest:
                    last_performed_date[m_name][t_name] = p_date

    # --- GENERATION LOGIC ---
    if st.button("🚀 Generate Schedule"):
        generated_rows = []

        for sat, s_idx in selected_saturdays:
            date_str = sat.strftime('%d/%m/%Y')
            
            active_group = None
            group_tasks = []
            if s_idx == 1:
                active_group, group_tasks = sabbath_1_group, sabbath_1_tasks
            elif s_idx == 2:
                active_group, group_tasks = sabbath_2_group, sabbath_2_tasks
            elif s_idx == 3:
                active_group, group_tasks = sabbath_3_group, sabbath_3_tasks
            elif s_idx == 4:
                active_group, group_tasks = sabbath_4_group, sabbath_4_tasks
            elif s_idx == 5:
                active_group, group_tasks = sabbath_5_group, sabbath_5_tasks

            task_scarcity = []
            for _, task in tasks_df.iterrows():
                t_id = str(task['id'])
                t_name = str(task['name'])
                
                if active_group and t_name in group_tasks:
                    competent_count = 0
                else:
                    competent_member_ids = competencies_df[competencies_df['tasks_id'].astype(str) == t_id]['member_id'].tolist()
                    eligible = members_df[(members_df['id'].isin(competent_member_ids)) & (members_df['available'] == True)]
                    competent_count = len(eligible)
                
                task_scarcity.append((task, competent_count))

            task_scarcity.sort(key=lambda x: x[1])

            assigned_on_this_sabbath = set()
            current_sabbath_assignments = set()
            sabbath_schedule = {}

            for task, _ in task_scarcity:
                t_id = str(task['id'])
                t_name = str(task['name'])
                
                if active_group and t_name in group_tasks:
                    assigned_person = active_group
                else:
                    competent_member_ids = competencies_df[competencies_df['tasks_id'].astype(str) == t_id]['member_id'].tolist()
                    eligible_df = members_df[(members_df['id'].isin(competent_member_ids)) & (members_df['available'] == True)]
                    
                    is_trimester_start_month = sat.month in [1, 4, 7, 10]
                    if t_name == "CUTL" and is_trimester_start_month and s_idx == elder_sabbath_choice:
                        if 'Elder' in members_df.columns:
                            elder_filter = members_df['Elder'].astype(str).str.upper().isin(['TRUE', 'YES', '1'])
                            elder_member_ids = members_df[elder_filter]['id'].tolist()
                            eligible_df = eligible_df[eligible_df['id'].isin(elder_member_ids)]

                    eligible = eligible_df['name'].tolist()
                    
                    if eligible:
                        not_yet_assigned = [m for m in eligible if m not in assigned_on_this_sabbath]
                        pool = not_yet_assigned if not_yet_assigned else eligible

                        rested_pool = [m for m in pool if m not in last_sabbath_assigned_members]
                        final_pool = rested_pool if rested_pool else pool

                        default_old_date = date(2000, 1, 1)
                        member_last_dates = {
                            m: last_performed_date.get(m, {}).get(t_name, default_old_date) 
                            for m in final_pool
                        }
                        
                        oldest_date = min(member_last_dates.values())
                        candidates = [m for m, d in member_last_dates.items() if d == oldest_date]
                        
                        assigned_person = np.random.choice(candidates)
                        
                        last_performed_date[assigned_person][t_name] = sat
                        assigned_on_this_sabbath.add(assigned_person)
                        current_sabbath_assignments.add(assigned_person)
                    else:
                        assigned_person = "Unassigned"

                sabbath_schedule[t_name] = assigned_person

            for _, task in tasks_df.iterrows():
                t_name = str(task['name'])
                generated_rows.append({
                    "Date": date_str,
                    "Task": t_name,
                    "AssignedMember": sabbath_schedule.get(t_name, "Unassigned")
                })
            
            last_sabbath_assigned_members = current_sabbath_assignments

        result_df = pd.DataFrame(generated_rows)
        st.success("✨ Schedule successfully generated!")
        st.dataframe(result_df, use_container_width=True)

        # --- AUTO-COMMIT TO GITHUB ---
        with st.spinner("Updating Planning.csv on GitHub..."):
            success, msg = update_github_csv(result_df)
            if success:
                st.balloons()
                st.success(f"🎉 {msg}")
            else:
                st.warning(f"⚠️ Manual Download Available. Auto-commit info: {msg}")

        csv_data = result_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Planning CSV (Backup)",
            data=csv_data,
            file_name="Generated_Planning.csv",
            mime="text/csv",
        )
else:
    st.info("👈 Please ensure `Members.csv`, `Competencies.csv`, and `Tasks.csv` exist in your repository or upload them in the sidebar.")
