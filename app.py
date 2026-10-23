import os
import json
import base64
import requests
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta, date

st.set_page_config(page_title="Church Schedule Generator", layout="wide")

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


# --- AUTOMATED PLANNING PRUNING ---
def prune_planning_data(planning_df, max_rows=1000):
    """Trims oldest Sabbath dates if Planning.csv exceeds max_rows to maintain peak performance."""
    if planning_df is None or len(planning_df) <= max_rows:
        return planning_df
    
    df_copy = planning_df.copy()
    df_copy['parsed_date'] = pd.to_datetime(df_copy['Date'], dayfirst=True, errors='coerce')
    unique_dates = sorted(df_copy['parsed_date'].dropna().dt.date.unique())
    
    while len(df_copy) > max_rows and len(unique_dates) > 50:
        oldest_date = unique_dates.pop(0)
        df_copy = df_copy[df_copy['parsed_date'].dt.date != oldest_date]
        
    return df_copy.drop(columns=['parsed_date'], errors='ignore')


# --- AUTO-PUBLISH PUBLIC HTML PAGE FOR GITHUB PAGES ---
def publish_public_schedule_page(planning_df, tasks_df, num_latest=3):
    """Generates a gorgeous, mobile-friendly card layout index.html respecting Tasks.csv order."""
    if planning_df is None or planning_df.empty:
        return
    
    task_desc_map = {}
    ordered_task_names = []
    if tasks_df is not None and 'name' in tasks_df.columns:
        ordered_task_names = [str(x).strip() for x in tasks_df['name'].dropna().tolist()]
        if 'description' in tasks_df.columns:
            task_desc_map = dict(zip(tasks_df['name'].astype(str).str.strip(), tasks_df['description'].fillna(tasks_df['name']).astype(str).str.strip()))

    df = planning_df.copy()
    df['parsed_date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df['CleanTask'] = df['Task'].astype(str).str.strip()
    
    valid_plan = df.dropna(subset=['parsed_date']).sort_values(by='parsed_date')
    unique_dates = valid_plan['parsed_date'].dt.date.unique()
    
    if len(unique_dates) == 0:
        return

    today = date.today()
    future_dates = [d for d in unique_dates if d >= today]
    reference_date = future_dates[0] if future_dates else unique_dates[-1]

    latest_dates_slice = list(unique_dates[-num_latest:])
    if reference_date not in latest_dates_slice:
        latest_dates_slice.append(reference_date)

    filtered_plan = valid_plan[valid_plan['parsed_date'].dt.date.isin(latest_dates_slice)].copy()
    
    # Sort tasks strictly according to Tasks.csv ordering
    if ordered_task_names:
        task_cat = pd.CategoricalDtype(categories=ordered_task_names, ordered=True)
        filtered_plan['TaskOrder'] = filtered_plan['CleanTask'].astype(task_cat)
        filtered_plan = filtered_plan.sort_values(by=['parsed_date', 'TaskOrder'])

    sabbath_cards_html = ""
    for d in sorted(latest_dates_slice):
        date_str = d.strftime('%d/%m/%Y')
        day_df = filtered_plan[filtered_plan['parsed_date'].dt.date == d]
        
        rows_html = ""
        for _, row in day_df.iterrows():
            t_code = str(row['CleanTask']).strip()
            t_display = task_desc_map.get(t_code, t_code)
            
            rows_html += f"""
            <div class="schedule-row">
                <span class="task-name">{t_display}</span>
                <span class="member-name">{str(row['AssignedMember']).strip()}</span>
            </div>
            """
            
        sabbath_cards_html += f"""
        <div class="sabbath-card">
            <div class="card-date-header">{date_str}</div>
            <div class="card-body">
                {rows_html}
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="mg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anjara Fanompoana Isan-Tsabata</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #f4f7f6;
            margin: 0;
            padding: 20px;
            color: #2c3e50;
        }}
        .container {{
            max-width: 650px;
            margin: auto;
        }}
        .main-title {{
            text-align: center;
            color: #1a252f;
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.5px;
            margin-top: 20px;
            margin-bottom: 25px;
            text-transform: uppercase;
            line-height: 1.3;
        }}
        .btn-print {{
            display: block;
            width: fit-content;
            margin: 0 auto 35px auto;
            background-color: #2c3e50;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: background 0.2s;
            text-decoration: none;
        }}
        .btn-print:hover {{
            background-color: #1a252f;
        }}
        .sabbath-card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            margin-bottom: 35px;
            border: 1px solid #e1e8ed;
        }}
        .card-date-header {{
            position: sticky;
            top: 10px;
            z-index: 10;
            background-color: #ffffff;
            color: #2980b9;
            padding: 16px;
            text-align: center;
            font-size: 20px;
            font-weight: 700;
            border-bottom: 2px solid #edf2f7;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.03);
            letter-spacing: 0.5px;
        }}
        .card-body {{
            padding: 0 20px 10px 20px;
        }}
        .schedule-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 0;
            border-bottom: 1px solid #f1f5f9;
        }}
        .schedule-row:last-child {{
            border-bottom: none;
        }}
        .task-name {{
            color: #7f8c8d;
            font-size: 15px;
            font-weight: 500;
            flex: 1;
            padding-right: 15px;
        }}
        .member-name {{
            color: #1a252f;
            font-size: 16px;
            font-weight: 700;
            text-align: right;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            font-size: 13px;
            color: #95a5a6;
            margin-bottom: 20px;
        }}
        @media print {{
            .btn-print {{ display: none; }}
            body {{ background-color: white; padding: 0; }}
            .sabbath-card {{ box-shadow: none; border: 1px solid #ccc; }}
            .card-date-header {{ position: static; box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="main-title">Anjara Fanompoana Isan-Tsabata</h1>
        
        <button class="btn-print" onclick="window.print()">📥 Haka ny PDF (Pirinty)</button>
        
        {sabbath_cards_html}
        
        <div class="footer">
            <p>Namboarina tamin'ny alalan'ny rafitra mandeha ho azy</p>
        </div>
    </div>
</body>
</html>
"""
    push_file_to_github("index.html", html_content, "Auto-publish index.html with task descriptions in Tasks.csv order")


# --- SIDEBAR: REFRESH & QUICK ACTIONS ---
st.sidebar.header("🛠️ System Controls")
if st.sidebar.button("🔄 Refresh App & Clear Cache"):
    st.cache_data.clear()
    st.rerun()

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
    def clean_s(val):
        return str(val).strip() if pd.notna(val) else ""

    task_id_to_name = {clean_s(r['id']): clean_s(r['name']) for _, r in tasks_df.iterrows()}
    task_name_to_id = {clean_s(r['name']): clean_s(r['id']) for _, r in tasks_df.iterrows()}
    task_names = [clean_s(x) for x in tasks_df['name'].dropna().tolist() if clean_s(x)]

    default_ss = [t for t in ["SSM", "SST", "SS5"] if t in task_names]
    default_cu = [t for t in ["SSM", "SST", "SS5", "CUM", "CUVK", "CUVP", "CUFN", "CUTA", "CUTL"] if t in task_names]

    # --- SIDEBAR SETTINGS ---
    st.sidebar.header("1. Planning Period & Settings")
    start_date_val = datetime.strptime(config_data.get("start_date", str(date.today())), "%Y-%m-%d").date() if "start_date" in config_data else date.today()
    start_date = st.sidebar.date_input("Start Date", value=start_date_val, key="start_date_input")
    num_sabbaths = st.sidebar.slider("Number of Sabbaths to Generate", min_value=1, max_value=10, value=config_data.get("num_sabbaths", 2), key="num_sabbaths_slider")

    max_planning_rows = st.sidebar.number_input("Max Planning Rows Limit (Auto-Prune)", min_value=200, max_value=5000, value=config_data.get("max_planning_rows", 1000), step=100, key="max_planning_rows_input")

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

    sabbath_3_group = st.sidebar.text_input("3rd Sabbath Group (Lehibe I for SSM, SST, SS5)", value=s3["group"], key="s3_g")
    sabbath_3_tasks = st.sidebar.multiselect("3rd Sabbath Group Tasks", options=task_names, default=[t for t in s3["tasks"] if t in task_names], key="s3_t")

    sabbath_4_group = st.sidebar.text_input("4th Sabbath Group", value=s4["group"], key="s4_g")
    sabbath_4_tasks = st.sidebar.multiselect("4th Sabbath Group Tasks", options=task_names, default=[t for t in s4["tasks"] if t in task_names], key="s4_t")

    sabbath_5_group = st.sidebar.text_input("5th Sabbath Group", value=s5["group"], key="s5_g")
    sabbath_5_tasks = st.sidebar.multiselect("5th Sabbath Group Tasks", options=task_names, default=[t for t in s5["tasks"] if t in task_names], key="s5_t")

    current_config = {
        "start_date": str(start_date),
        "num_sabbaths": num_sabbaths,
        "max_planning_rows": max_planning_rows,
        "elder_sabbath_choice": elder_sabbath_choice,
        "s1": {"group": sabbath_1_group, "tasks": sabbath_1_tasks},
        "s2": {"group": sabbath_2_group, "tasks": sabbath_2_tasks},
        "s3": {"group": sabbath_3_group, "tasks": sabbath_3_tasks},
        "s4": {"group": sabbath_4_group, "tasks": sabbath_4_tasks},
        "s5": {"group": sabbath_5_group, "tasks": sabbath_5_tasks},
    }
    if current_config != config_data:
        save_config_to_github(current_config)

    # --- MAIN NAVIGATION TABS ---
    tab_gen, tab_analytics, tab_crud, tab_view = st.tabs([
        "🚀 Schedule Generator & Quick Swap", 
        "🔍 Rotation Analytics & Query",
        "📊 Data Management (CRUD)", 
        "👥 Member Schedule View"
    ])

    if planning_df is not None and not planning_df.empty:
        planning_df['parsed_date'] = pd.to_datetime(planning_df['Date'], dayfirst=True, errors='coerce')
        planning_df['CleanMember'] = planning_df['AssignedMember'].astype(str).str.strip()
        planning_df['CleanTask'] = planning_df['Task'].astype(str).str.strip()
        planning_df['NormalizedTask'] = planning_df['CleanTask'].apply(lambda x: task_id_to_name.get(x, x))

    # Detailed history lookup function with overall activity fallback
    def get_member_task_history_info(p_df, member_name, task_name):
        if p_df is None or p_df.empty:
            return None, "Never"
        
        m_upper = member_name.strip().upper()
        t_upper = task_name.strip().upper()
        t_id = task_name_to_id.get(task_name, "").upper()
        
        task_sub = p_df[
            (p_df['CleanMember'].str.upper() == m_upper) &
            (
                (p_df['CleanTask'].str.upper() == t_upper) |
                (p_df['CleanTask'].str.upper() == t_id) |
                (p_df['NormalizedTask'].str.upper() == t_upper)
            )
        ].dropna(subset=['parsed_date'])
        
        if not task_sub.empty:
            max_d = task_sub['parsed_date'].max().date()
            return max_d, max_d.strftime('%d/%m/%Y')
        
        # Fallback: check if member has done ANY task in the past
        member_sub = p_df[p_df['CleanMember'].str.upper() == m_upper].dropna(subset=['parsed_date'])
        if not member_sub.empty:
            last_any_row = member_sub.sort_values(by='parsed_date', ascending=False).iloc[0]
            any_d_str = last_any_row['parsed_date'].strftime('%d/%m/%Y')
            any_task = last_any_row['Task']
            return None, f"Never done {task_name} (Last active: {any_d_str} on {any_task})"
        
        return None, "Never"

    # ================= TAB 1: SCHEDULE GENERATOR & QUICK SWAP =================
    with tab_gen:
        st.title("⛪ Church Schedule Planning Generator")
        st.markdown("Automated fair-rotation church scheduling with persistent cloud settings and GitHub sync.")

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

        # Historical Tracking
        available_members = [clean_s(m) for m in members_df[members_df['available'] == True]['name'].tolist()]
        last_performed_date = {m: {} for m in available_members}
        last_sabbath_assigned_members = set()

        existing_dates = set()
        if planning_df is not None and not planning_df.empty:
            existing_dates = set(planning_df['parsed_date'].dt.date.dropna())
            
            if not planning_df['parsed_date'].isna().all():
                max_date = planning_df['parsed_date'].max()
                last_sabbath_rows = planning_df[planning_df['parsed_date'] == max_date]
                last_sabbath_assigned_members = set(last_sabbath_rows['CleanMember'].dropna())

            for _, row in planning_df.iterrows():
                m_name = str(row.get('CleanMember', '')).strip()
                t_val = str(row.get('CleanTask', '')).strip()
                t_name = task_id_to_name.get(t_val, t_val)
                p_date_raw = row.get('parsed_date')
                
                if m_name in last_performed_date and pd.notna(p_date_raw):
                    p_date = pd.to_datetime(p_date_raw).date()
                    current_latest = last_performed_date[m_name].get(t_name)
                    if current_latest is None or p_date > current_latest:
                        last_performed_date[m_name][t_name] = p_date

        if st.button("🚀 Generate Schedule"):
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
                        t_id = clean_s(task['id'])
                        t_name = clean_s(task['name'])
                        
                        if active_group and t_name in group_tasks:
                            competent_count = 0
                        else:
                            competent_member_ids = competencies_df[competencies_df['tasks_id'].astype(str).str.strip() == t_id]['member_id'].tolist()
                            eligible = members_df[(members_df['id'].isin(competent_member_ids)) & (members_df['available'] == True)]
                            
                            if s_idx == 3 and 'Youth' in members_df.columns:
                                youth_mask = members_df['Youth'].astype(str).str.upper().isin(['TRUE', 'YES', '1']) | (members_df['Youth'] == True)
                                eligible = eligible[youth_mask]
                                
                            competent_count = len(eligible)
                        
                        task_scarcity.append((task, competent_count))

                    task_scarcity.sort(key=lambda x: x[1])

                    assigned_on_this_sabbath = set()
                    current_sabbath_assignments = set()
                    sabbath_schedule = {}

                    for task, _ in task_scarcity:
                        t_id = clean_s(task['id'])
                        t_name = clean_s(task['name'])
                        
                        if active_group and t_name in group_tasks:
                            assigned_person = active_group
                        else:
                            competent_member_ids = competencies_df[competencies_df['tasks_id'].astype(str).str.strip() == t_id]['member_id'].tolist()
                            eligible_df = members_df[(members_df['id'].isin(competent_member_ids)) & (members_df['available'] == True)]
                            
                            if s_idx == 3 and 'Youth' in members_df.columns:
                                youth_mask = members_df['Youth'].astype(str).str.upper().isin(['TRUE', 'YES', '1']) | (members_df['Youth'] == True)
                                eligible_df = eligible_df[youth_mask]

                            is_trimester_start_month = sat.month in [1, 4, 7, 10]
                            if t_name == "CUTL" and is_trimester_start_month and s_idx == elder_sabbath_choice and s_idx != 3:
                                if 'Elder' in members_df.columns:
                                    elder_filter = members_df['Elder'].astype(str).str.upper().isin(['TRUE', 'YES', '1']) | (members_df['Elder'] == True)
                                    elder_member_ids = members_df[elder_filter]['id'].tolist()
                                    eligible_df = eligible_df[eligible_df['id'].isin(elder_member_ids)]

                            eligible = [clean_s(m) for m in eligible_df['name'].tolist()]
                            
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
                        t_name = clean_s(task['name'])
                        generated_rows.append({
                            "Date": date_str,
                            "Task": t_name,
                            "AssignedMember": sabbath_schedule.get(t_name, "Unassigned")
                        })
                    
                    last_sabbath_assigned_members = current_sabbath_assignments

                result_df = pd.DataFrame(generated_rows)
                st.success("✨ Schedule successfully generated for new dates!")
                st.dataframe(result_df, use_container_width=True)

                with st.spinner("Updating Planning.csv, auto-pruning old history, and publishing web page..."):
                    if planning_df is not None and not planning_df.empty:
                        base_planning_df = planning_df.drop(columns=['parsed_date', 'CleanMember', 'CleanTask', 'NormalizedTask'], errors='ignore')
                    else:
                        base_planning_df = pd.DataFrame(columns=["Date", "Task", "AssignedMember"])

                    updated_planning_df = pd.concat([base_planning_df, result_df], ignore_index=True)
                    updated_planning_df = prune_planning_data(updated_planning_df, max_rows=max_planning_rows)
                    
                    success_csv = push_file_to_github("Planning.csv", updated_planning_df.to_csv(index=False), "Auto-update & prune Planning.csv")
                    publish_public_schedule_page(updated_planning_df, tasks_df, num_latest=num_sabbaths)

                    if success_csv:
                        st.balloons()
                        st.success("🎉 Successfully updated Planning.csv, pruned old history, and published the public webpage!")
                    else:
                        st.warning("⚠️ Auto-commit failed, but you can download the CSV manually below.")

                csv_data = result_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Generated Planning CSV (Backup)",
                    data=csv_data,
                    file_name="Generated_Planning.csv",
                    mime="text/csv",
                )

        # --- EMERGENCY REPLACEMENT & VISITOR TASK SWAP TOOL ---
        st.markdown("---")
        st.subheader("🚑 Smart Emergency Replacement & Visitor Swap")
        st.markdown("Select a Sabbath and task to view intelligent candidate recommendations (sorted oldest-first by last performed date).")

        if planning_df is not None and not planning_df.empty:
            available_dates_list = sorted(planning_df['parsed_date'].dropna().dt.date.unique(), reverse=True)
            
            if available_dates_list:
                selected_swap_date = st.selectbox("Select Sabbath Date to Modify", options=available_dates_list, format_func=lambda x: x.strftime('%d/%m/%Y'), key="swap_date_sel")
                
                date_str_fmt = selected_swap_date.strftime('%d/%m/%Y')
                sub_df = planning_df[planning_df['parsed_date'].dt.date == selected_swap_date]
                
                # Order drop down options according to Tasks.csv
                task_options = [t for t in task_names if t in sub_df['NormalizedTask'].unique()]
                selected_swap_task = st.selectbox("Select Task / Role", options=task_options, key="swap_task_sel")
                
                current_assigned = sub_df[sub_df['NormalizedTask'] == selected_swap_task]['CleanMember'].values
                current_person = current_assigned[0] if len(current_assigned) > 0 else "Unknown"
                st.info(f"Current assigned person for **{selected_swap_task}** on **{date_str_fmt}**: **{current_person}**")
                
                # Ranked Smart Recommendation Engine
                recommended_members_ranked = []
                
                if members_df is not None and competencies_df is not None:
                    t_id = task_name_to_id.get(selected_swap_task, "")
                    competent_member_ids = competencies_df[competencies_df['tasks_id'].astype(str).str.strip() == t_id]['member_id'].tolist() if t_id else []
                    eligible_df = members_df[members_df['id'].isin(competent_member_ids)] if competent_member_ids else members_df.copy()
                    eligible_df = eligible_df[eligible_df['available'] == True]
                    
                    first_day_of_month = date(selected_swap_date.year, selected_swap_date.month, 1)
                    first_sat = first_day_of_month + timedelta(days=(5 - first_day_of_month.weekday()) % 7)
                    s_idx = ((selected_swap_date - first_sat).days // 7) + 1
                    
                    if s_idx == 3 and 'Youth' in members_df.columns:
                        youth_mask = members_df['Youth'].astype(str).str.upper().isin(['TRUE', 'YES', '1']) | (members_df['Youth'] == True)
                        eligible_df = eligible_df[youth_mask]
                        
                    eligible_names = [clean_s(m) for m in eligible_df['name'].tolist()]
                    
                    member_scores = []
                    default_past_date = date(2000, 1, 1)
                    
                    for m in eligible_names:
                        last_d, d_str = get_member_task_history_info(planning_df, m, selected_swap_task)
                        sort_d = last_d if last_d else default_past_date
                        member_scores.append((m, sort_d, d_str))
                    
                    member_scores.sort(key=lambda x: x[1])
                    
                    for m, _, d_str in member_scores:
                        recommended_members_ranked.append((m, f"{m} (Last done: {d_str})"))

                swap_mode = st.radio("Replacement Type", options=["Recommended Church Member (Sorted Oldest-First)", "All Members List", "Custom Visitor / Guest (e.g., Visiting Pastor)"], key="swap_mode_radio")
                
                new_assignee = ""
                if swap_mode == "Recommended Church Member (Sorted Oldest-First)":
                    if recommended_members_ranked:
                        st.success(f"✨ **Smart Recommendations** (Sorted by longest time since last performed task):")
                        chosen_tuple = st.selectbox(
                            "Select Best Available Replacement", 
                            options=recommended_members_ranked, 
                            format_func=lambda x: x[1],
                            key="swap_recommended_sel"
                        )
                        new_assignee = chosen_tuple[0]
                    else:
                        st.warning("⚠️ No competent/available members found matching criteria for this task.")
                        new_assignee = st.selectbox("Select Replacement Member", options=[clean_s(m) for m in members_df['name'].tolist()] if members_df is not None else [], key="swap_all_fallback_sel")
                elif swap_mode == "All Members List":
                    all_member_names = [clean_s(m) for m in members_df['name'].tolist()] if members_df is not None else []
                    new_assignee = st.selectbox("Select Replacement Member", options=all_member_names, key="swap_member_sel")
                else:
                    new_assignee = st.text_input("Enter Guest / Visitor Name", value="Visiting Pastor", key="swap_guest_text")
                
                if st.button("🔄 Apply Task Swap"):
                    if new_assignee:
                        mask = (planning_df['parsed_date'].dt.date == selected_swap_date) & (planning_df['NormalizedTask'].str.upper() == selected_swap_task.upper())
                        planning_df.loc[mask, 'AssignedMember'] = new_assignee
                        
                        clean_planning_df = planning_df.drop(columns=['parsed_date', 'CleanMember', 'CleanTask', 'NormalizedTask'], errors='ignore')
                        
                        with st.spinner("Applying swap and updating GitHub..."):
                            success_swap = push_file_to_github("Planning.csv", clean_planning_df.to_csv(index=False), f"Emergency swap: {selected_swap_task} on {date_str_fmt} to {new_assignee}")
                            publish_public_schedule_page(clean_planning_df, tasks_df, num_latest=num_sabbaths)
                            
                            if success_swap:
                                st.success(f"✅ Successfully swapped **{selected_swap_task}** to **{new_assignee}** for {date_str_fmt}! Public webpage updated.")
                                st.rerun()
                            else:
                                st.error("❌ Failed to update GitHub. Check your token permissions.")

                # --- EMBEDDED MEMBER ASSIGNMENT HISTORY ---
                if swap_mode != "Custom Visitor / Guest (e.g., Visiting Pastor)" and new_assignee:
                    st.markdown("---")
                    st.subheader(f"👤 Member Schedule History: {new_assignee}")
                    st.caption("Review past tasks and dates assigned to this member before/after swapping:")
                    
                    valid_p_df = planning_df.dropna(subset=['parsed_date']).sort_values(by='parsed_date', ascending=False)
                    m_history_df = valid_p_df[valid_p_df['CleanMember'].str.upper() == new_assignee.strip().upper()]
                    
                    if not m_history_df.empty:
                        m_display_df = m_history_df[['Date', 'Task']].copy()
                        m_display_df.columns = ['Daty (Date)', 'Andraikitra (Task)']
                        st.dataframe(m_display_df, use_container_width=True, hide_index=True)
                    else:
                        st.info(f"No past assignment records found for {new_assignee}.")
            else:
                st.info("No dated planning records available for swapping.")
        else:
            st.info("Planning history is empty.")

    # ================= TAB 2: ROTATION ANALYTICS & QUERY =================
    with tab_analytics:
        st.title("🔍 Rotation Analytics & Query")
        st.markdown("Query historical assignments and member rotation history (replicating your spreadsheet lookup filter).")

        if planning_df is not None and not planning_df.empty:
            valid_p_df = planning_df.dropna(subset=['parsed_date']).sort_values(by='parsed_date', ascending=False)
            
            col_left, col_right = st.columns(2)
            
            # --- FILTER 1: WHO DOES WHAT WHEN? (TASK VIEW) ---
            with col_left:
                st.subheader("📋 Task History: Who does what when?")
                sel_task_query = st.selectbox("Select Fanompoana (Task)", options=task_names, key="query_task_sel")
                
                if members_df is not None and competencies_df is not None:
                    t_id_q = task_name_to_id.get(sel_task_query, "")
                    comp_m_ids = competencies_df[competencies_df['tasks_id'].astype(str).str.strip() == t_id_q]['member_id'].tolist() if t_id_q else []
                    comp_members = [clean_s(m) for m in members_df[members_df['id'].isin(comp_m_ids)]['name'].tolist()] if comp_m_ids else [clean_s(m) for m in members_df['name'].tolist()]
                    
                    query_rows = []
                    default_p_date = date(2000, 1, 1)
                    
                    for m in comp_members:
                        last_d, d_display = get_member_task_history_info(valid_p_df, m, sel_task_query)
                        sort_d = last_d if last_d else default_p_date
                        query_rows.append({"Anarana (Member)": m, "Daty farany (Last Date)": d_display, "_sort": sort_d})
                    
                    query_result_df = pd.DataFrame(query_rows).sort_values(by="_sort", ascending=True).drop(columns=['_sort'])
                    st.markdown(f"**Competent Members for {sel_task_query} (Sorted Oldest-First):**")
                    st.dataframe(query_result_df, use_container_width=True, hide_index=True)
            
            # --- FILTER 2: WHEN DOES A MEMBER DO A TASK? (MEMBER VIEW) ---
            with col_right:
                st.subheader("👤 Member History: When does a member do tasks?")
                all_m_names = sorted([clean_s(m) for m in members_df['name'].dropna().unique().tolist()]) if members_df is not None else []
                sel_member_query = st.selectbox("Select Anarana (Member)", options=all_m_names, key="query_member_sel")
                
                m_history_df = valid_p_df[valid_p_df['CleanMember'].str.upper() == sel_member_query.upper()]
                
                if not m_history_df.empty:
                    m_display_df = m_history_df[['Date', 'Task']].copy()
                    m_display_df.columns = ['Daty (Date)', 'Andraikitra (Task)']
                    st.markdown(f"**Assignment History for {sel_member_query}:**")
                    st.dataframe(m_display_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No past assignment records found for {sel_member_query}.")
        else:
            st.info("No planning history available yet. Generate a schedule first!")

    # ================= TAB 3: DATA MANAGEMENT (CRUD) =================
    with tab_crud:
        st.title("📊 Data Management (Worksheet Editor)")
        st.markdown("View and edit your datasets directly. Changes are saved and committed straight to GitHub instantly.")

        dataset_choice = st.selectbox("Select Dataset to Edit", ["Members.csv", "Competencies.csv", "Tasks.csv", "Planning.csv"])
        
        current_df = load_github_csv(dataset_choice)
        if current_df is not None:
            st.markdown(f"Editing **{dataset_choice}**:")
            edited_df = st.data_editor(current_df, num_rows="dynamic", use_container_width=True, key=f"editor_{dataset_choice}")

            if st.button(f"💾 Save changes to {dataset_choice}"):
                if dataset_choice == "Planning.csv":
                    edited_df = prune_planning_data(edited_df, max_rows=max_planning_rows)
                    
                csv_string = edited_df.to_csv(index=False)
                with st.spinner(f"Pushing {dataset_choice} update to GitHub..."):
                    success = push_file_to_github(dataset_choice, csv_string, f"Manual CRUD update on {dataset_choice}")
                    if dataset_choice == "Planning.csv" and success:
                        publish_public_schedule_page(edited_df, tasks_df, num_latest=num_sabbaths)

                    if success:
                        st.success(f"✅ Successfully updated {dataset_choice} in GitHub!")
                    else:
                        st.error(f"❌ Failed to update {dataset_choice}. Check your token permissions.")
        else:
            st.warning(f"Could not load {dataset_choice}.")

    # ================= TAB 4: MEMBER SCHEDULE VIEW =================
    with tab_view:
        st.title("👥 Member Schedule View")
        st.markdown("Internal preview of what church members will see on the public web page.")

        if planning_df is not None and not planning_df.empty:
            valid_plan = planning_df.dropna(subset=['parsed_date']).sort_values(by='parsed_date')

            unique_dates = valid_plan['parsed_date'].dt.date.unique()

            if len(unique_dates) > 0:
                num_latest_to_show = st.slider("Number of latest Sabbath batches to display", min_value=1, max_value=5, value=3)
                
                today = date.today()
                future_dates = [d for d in unique_dates if d >= today]
                reference_date = future_dates[0] if future_dates else unique_dates[-1]

                latest_dates_slice = list(unique_dates[-num_latest_to_show:])
                if reference_date not in latest_dates_slice:
                    latest_dates_slice.append(reference_date)

                filtered_plan = valid_plan[valid_plan['parsed_date'].dt.date.isin(latest_dates_slice)].copy()
                
                # Apply Tasks.csv ordering to pivot rows
                if task_names:
                    task_cat = pd.CategoricalDtype(categories=task_names, ordered=True)
                    filtered_plan['TaskOrder'] = filtered_plan['NormalizedTask'].astype(task_cat)
                    filtered_plan = filtered_plan.sort_values(by='TaskOrder')

                display_df = filtered_plan.drop(columns=['parsed_date', 'CleanMember', 'CleanTask', 'NormalizedTask', 'TaskOrder'], errors='ignore')

                st.info(f"Displaying schedule for the most recent {num_latest_to_show} Sabbath generation(s) + nearest coming reference Sabbath.")
                
                pivot_df = display_df.pivot(index='Task', columns='Date', values='AssignedMember')
                if task_names:
                    pivot_df = pivot_df.reindex([t for t in task_names if t in pivot_df.index])
                st.dataframe(pivot_df, use_container_width=True)
            else:
                st.info("No valid dated planning records found yet.")
        else:
            st.info("No planning history available yet. Generate a schedule first!")

else:
    st.error("❌ Could not load required dataset files (`Members.csv`, `Competencies.csv`, or `Tasks.csv`) from your GitHub repository.")
