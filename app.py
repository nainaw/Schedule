import os
import json
import streamlit as st
from datetime import datetime, date
from utils.github_helpers import get_github_repo_file
from utils.scheduling_logic import prune_planning_data
from components.tab_generator import render_generator_tab
from components.tab_analytics import render_analytics_tab
from components.tab_crud import render_crud_tab
from components.tab_view import render_view_tab

st.set_page_config(page_title="Church Schedule Generator", layout="wide")

st.sidebar.header("🛠️ System Controls")
if st.sidebar.button("🔄 Refresh App & Clear Cache"):
    st.cache_data.clear()
    st.rerun()

config_data = {}
config_str, _, _ = get_github_repo_file("config.json")
if config_str:
    try:
        config_data = json.loads(config_str)
    except:
        pass

def load_github_csv(filename):
    content, _, _ = get_github_repo_file(filename)
    if content:
        return pd.read_csv(pd.io.common.StringIO(content))
    elif os.path.exists(filename):
        return pd.read_csv(filename)
    return None

import pandas as pd
members_df = load_github_csv("Members.csv")
competencies_df = load_github_csv("Competencies.csv")
tasks_df = load_github_csv("Tasks.csv")
planning_df = load_github_csv("Planning.csv")

if members_df is not None and competencies_df is not None and tasks_df is not None:
    task_names = [str(x).strip() for x in tasks_df['name'].dropna().tolist() if str(x).strip()]
    default_ss = [t for t in ["SSM", "SST", "SS5"] if t in task_names]
    default_cu = [t for t in ["SSM", "SST", "SS5", "CUM", "CUVK", "CUVP", "CUFN", "CUTA", "CUTL"] if t in task_names]

    st.sidebar.header("1. Planning Period & Settings")
    start_date_val = datetime.strptime(config_data.get("start_date", str(date.today())), "%Y-%m-%d").date() if "start_date" in config_data else date.today()
    start_date = st.sidebar.date_input("Start Date", value=start_date_val)
    num_sabbaths = st.sidebar.slider("Number of Sabbaths to Generate", 1, 10, config_data.get("num_sabbaths", 2))
    max_planning_rows = st.sidebar.number_input("Max Planning Rows Limit", 200, 5000, config_data.get("max_planning_rows", 1000), step=100)

    st.sidebar.header("2. Special Rules Configuration")
    elder_sabbath_choice = st.sidebar.selectbox("Reserve CUTL for Elder on which Sabbath?", [1, 2, 3, 4, 5], index=[1, 2, 3, 4, 5].index(config_data.get("elder_sabbath_choice", 2)))

    st.sidebar.header("3. Group Rule Configuration")
    s1 = config_data.get("s1", {"group": "Tanora Zokiny", "tasks": default_ss})
    s2 = config_data.get("s2", {"group": "Zatovo", "tasks": default_ss})
    s3 = config_data.get("s3", {"group": "Lehibe I", "tasks": default_ss})
    s4 = config_data.get("s4", {"group": "Lehibe II", "tasks": default_ss})
    s5 = config_data.get("s5", {"group": "MINENF", "tasks": default_cu})

    current_config = {
        "start_date": str(start_date),
        "num_sabbaths": num_sabbaths,
        "max_planning_rows": max_planning_rows,
        "elder_sabbath_choice": elder_sabbath_choice,
        "s1": {"group": st.sidebar.text_input("1st Sabbath Group", value=s1["group"]), "tasks": st.sidebar.multiselect("1st Sabbath Tasks", task_names, default=[t for t in s1["tasks"] if t in task_names])},
        "s2": {"group": st.sidebar.text_input("2nd Sabbath Group", value=s2["group"]), "tasks": st.sidebar.multiselect("2nd Sabbath Tasks", task_names, default=[t for t in s2["tasks"] if t in task_names])},
        "s3": {"group": st.sidebar.text_input("3rd Sabbath Group", value=s3["group"]), "tasks": st.sidebar.multiselect("3rd Sabbath Tasks", task_names, default=[t for t in s3["tasks"] if t in task_names])},
        "s4": {"group": st.sidebar.text_input("4th Sabbath Group", value=s4["group"]), "tasks": st.sidebar.multiselect("4th Sabbath Tasks", task_names, default=[t for t in s4["tasks"] if t in task_names])},
        "s5": {"group": st.sidebar.text_input("5th Sabbath Group", value=s5["group"]), "tasks": st.sidebar.multiselect("5th Sabbath Tasks", task_names, default=[t for t in s5["tasks"] if t in task_names])},
    }
    
    if current_config != config_data:
        from utils.github_helpers import push_file_to_github
        push_file_to_github("config.json", json.dumps(current_config, indent=4), "Update config")

    tab_gen, tab_analytics, tab_crud, tab_view = st.tabs([
        "🚀 Schedule Generator & Quick Swap", 
        "🔍 Rotation Analytics & Query",
        "📊 Data Management (CRUD)", 
        "👥 Member Schedule View"
    ])

    with tab_gen:
        render_generator_tab(members_df, competencies_df, tasks_df, planning_df, current_config)
    with tab_analytics:
        render_analytics_tab(members_df, competencies_df, tasks_df, planning_df)
    with tab_crud:
        render_crud_tab(tasks_df, max_planning_rows)
    with tab_view:
        render_view_tab(planning_df, tasks_df)
else:
    st.error("❌ Could not load required dataset files from GitHub.")