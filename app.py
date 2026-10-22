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
st.markdown("Automated fair-rotation church scheduling with persistent cloud settings and GitHub sync.")

# --- GITHUB API HELPERS ---
def get_github_repo_file(file_path):
    """Fetches raw content and sha of a file from GitHub (tries main, then master)."""
    if "GITHUB_TOKEN" not in st.secrets or "REPO_NAME" not in st.secrets:
        return None, None, None

    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["REPO_NAME"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

    for branch in ["main", "master"]:
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, data["sha"], branch
    return None, None, "main"

def push_file_to_github(file_path, content_str, commit_message):
    """Pushes or updates a file directly in the GitHub repository."""
    if "GITHUB_TOKEN" not in st.secrets or "REPO_NAME" not in st.secrets:
        return False

    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["REPO_NAME"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

    _, sha, branch = get_github_repo_file(file_path)
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    
    encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    payload = {
        "message": commit_message,
        "content": encoded,
        "branch": branch
    }
    if sha:
        payload["sha"] = sha

    res = requests.put(url, headers=headers, data=json.dumps(payload))
    return res.status_code in [200, 201]


# --- LOAD CONFIG.JSON FROM GITHUB ---
config_data = {}
config_str, _, _ = get_github_repo_file("config.json")
if config_str:
    try:
        config_data = json.loads(config_str)
    except:
        config_data = {}

def save_config_to_github(new_config):
    push_file_to_github("config.json", json.dumps(new_config, indent=4), "Update app configuration")


# --- LOAD DATASETS DIRECTLY FROM GITHUB ---
def load_github_csv(filename):
    content, _, _ = get_github_repo_file(filename)
    if content:
        return pd.read_csv(pd.io.common.StringIO(content))
    elif os.path.exists(filename):
        return pd.read_csv(filename)
    return None

members_df = load_github_csv("Members.csv")
competencies_df = load_github_csv("Competencies.csv")
tasks_df = load_github_csv("Tasks.csv")
planning_df = load_github_csv("Planning.csv")

if members_df is not None and competencies_df is not None and tasks_df is not None:
    task_id_to_name = dict(zip(tasks_df['id'].astype(str), tasks_df['name'].astype(str)))
    task_names = tasks_df['name'].dropna().astype(str).tolist()

    default_ss = [t for t in ["SSM", "SST", "SS5"] if t in task_names]
    default_cu = [t for t in ["SSM", "SST", "SS5", "CUM", "CUVK", "CUVP", "CUFN", "CUTA", "CUTL"] if t in task_names]

    # --- SIDEBAR SETTINGS (LOADED FROM GITHUB CONFIG) ---
    st.sidebar.header("1. Planning Period & Settings")
    start_date_val = datetime.strptime(config_data.get("start_date", str(date.today())), "%Y-%m-%d").date() if "start_date" in config_data else date.today()
    start_date = st.sidebar.date_input("Start Date", value=start_date_val, key="start_date_input")
    num_sabbaths = st.sidebar.slider("Number of Sabbaths to Generate", min_value=1, max_value=10, value=config_data.get("num_sabbaths", 2), key="num_sabbaths_slider")

    st.sidebar.header("2. Special Rules Configuration")
    elder_options = [1, 2, 3, 4, 5]
    saved_elder_choice = config_data.get("elder_sabbath_choice", 2)
    if saved_elder_choice not in elder_options:
        saved_elder_choice = 2

    if "elder_sabbath_select" not in st.session_state:
        st.session_state["elder_sabbath_select"] = saved_elder_choice

    elder_sabbath_choice = st.sidebar.selectbox(
        "Reserve CUTL for Elder on which Sabbath of Trimester Start Months?",
        options=elder_options,
        index=elder_options.index(st.session_state["elder_sabbath_select"]),
        key="elder_sabbath_select"
    )

    st.sidebar.header("3. Group Rule Configuration")
    s1 = config_data.get("s1", {"group": "Tanora Zokiny", "tasks": default_ss})
    s2 = config_data.get("s2", {"group": "Zatovo", "tasks": default_ss})
    s3 = config_data.get("s3", {"group": "Lehibe I", "tasks": default_ss})
    s4 = config_data.get("s4", {"group": "Lehibe II", "tasks": default_ss})
    s5 = config_data.get("s5", {"group": "MINENF", "tasks": default_cu})

    sabbath_1_group = st.sidebar.text_input("1st Sabbath Group", value=s1["group"], key="s1_g")
    sabbath_1_tasks = st.sidebar.multiselect("1st Sabbath Group Tasks", options=task_names, default=[t for t in s1["tasks"] if t in task_names], key="s1_t")

    sabbath_2_group = st.sidebar.text_input("2nd Sabbath Group", value=s2["group"], key="s2_g")
    sabbath_2_tasks = st.sidebar.multiselect("2nd Sabbath Group Tasks", options=task_names, default=[t for t in s2["tasks"] if t in task_names], key="s2_t")

    sabbath_3_group = st.sidebar.text_input("3rd Sabbath Group", value=s3["group"], key="s3_g")
    sabbath_3_tasks = st.sidebar.multiselect("3rd Sabbath Group Tasks", options=task_names, default=[t for t in s3["tasks"] if t in task_names], key="s3_t")

    sabbath_4_group = st.sidebar.text_input("4th Sabbath Group", value=s4["group"], key="s4_g")
    sabbath_4_tasks = st.sidebar.multiselect("4th Sabbath Group Tasks", options=task_names, default=[t for t in s4["tasks"] if t in task_names], key="s4_t")

    sabbath_5_group = st.sidebar.text_input("5th Sabbath Group", value=s5["group"], key="s5_g")
    sabbath_5_tasks = st.sidebar.multiselect("5th Sabbath Group Tasks", options=task_names, default=[t for t in s5["tasks"] if t in task_names], key="s5_t")

    # Save current configuration back to GitHub config.json automatically on change
    current_config = {
        "start_date": str(start_date),
        "num_sabbaths": num_sabbaths,
        "elder_sabbath_choice": elder_sabbath_choice,
        "s1": {"group": sabbath_1_group, "tasks": sabbath_1_tasks},
        "s2": {"group": sabbath_2_group, "tasks": sabbath_2_tasks},
        "s3": {"group": sabbath_3_group, "tasks": sabbath_3_tasks},
        "s4": {"group": sabbath_4_group, "tasks": sabbath_4_tasks},
        "s5": {"group": sabbath_5_group, "tasks": sabbath_5_tasks},
    }
    if current_config != config_data:
        save_config_to_github(current_config)

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

    existing_planning_str, _, _ = get_github_repo_file("Planning.csv")
    if existing_planning_str:
        planning_df = pd.read_csv(pd.io.common.StringIO(existing_planning_str))

    existing_dates = set()
    if planning_df is not None and not planning_df.empty:
        planning_df['parsed_date'] = pd.to_datetime(planning_df['Date'], format='%d/%m/%Y', errors='coerce')
        existing_dates = set(planning_df['parsed_date'].dt.date.dropna())
        
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
        # Filter out dates that already exist in Planning.csv
        valid_saturdays = []
        skipped_dates = []
        
        for sat, s_idx in selected_saturdays:
            if sat in existing_dates:
                skipped_dates.append(sat.strftime('%d/%m/%Y'))
            else:
                valid_saturdays.append((sat, s_idx))

        if skipped_dates:
            st.warning(f"⚠️ Notice: Schedule generation skipped for the following dates because they already exist in `Planning.csv`: **{', '.join(skipped_dates)}**")

        if not valid_saturdays:
            st.info("ℹ️ All selected Sabbath dates already exist in your Planning history. No new schedules needed to be generated.")
        else:
            generated_rows = []

            for sat, s_idx in valid_saturdays:
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
            st.success("✨ Schedule successfully generated for new dates!")
            st.dataframe(result_df, use_container_width=True)

            # --- AUTO-COMMIT PLANNING.CSV TO GITHUB ---
            with st.spinner("Updating Planning.csv on GitHub..."):
                if planning_df is not None and not planning_df.empty:
                    # Drop temporary parsed_date column before concatenation
                    base_planning_df = planning_df.drop(columns=['parsed_date'], errors='ignore')
                else:
                    base_planning_df = pd.DataFrame(columns=["Date", "Task", "AssignedMember"])

                updated_planning_df = pd.concat([base_planning_df, result_df], ignore_index=True)
                success = push_file_to_github("Planning.csv", updated_planning_df.to_csv(index=False), "Auto-update Planning.csv with new Sabbaths")

                if success:
                    st.balloons()
                    st.success("🎉 Successfully updated Planning.csv in your GitHub repository!")
                else:
                    st.warning("⚠️ Auto-commit failed, but you can download the CSV manually below.")

            csv_data = result_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Generated Planning CSV (Backup)",
                data=csv_data,
                file_name="Generated_Planning.csv",
                mime="text/csv",
            )
else:
    st.error("❌ Could not load required dataset files (`Members.csv`, `Competencies.csv`, or `Tasks.csv`) from your GitHub repository. Please ensure they are present in the repository root directory.")
