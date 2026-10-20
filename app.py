import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta, date

st.set_page_config(page_title="Church Schedule Generator", layout="wide")

st.title("⛪ Church Schedule Planning Generator")
st.markdown("Upload your datasets, customize group rules and Sabbath dates, and automatically generate the fair-rotation planning sheet.")

# --- SIDEBAR: FILE UPLOADS ---
st.sidebar.header("1. Upload CSV Files")
uploaded_members = st.sidebar.file_uploader("Members.csv", type=["csv"])
uploaded_competencies = st.sidebar.file_uploader("Competencies.csv", type=["csv"])
uploaded_tasks = st.sidebar.file_uploader("Tasks.csv", type=["csv"])
uploaded_planning = st.sidebar.file_uploader("Planning.csv (History for Rotation)", type=["csv"])

if uploaded_members and uploaded_competencies and uploaded_tasks:
    members_df = pd.read_csv(uploaded_members)
    competencies_df = pd.read_csv(uploaded_competencies)
    tasks_df = pd.read_csv(uploaded_tasks)
    planning_df = pd.read_csv(uploaded_planning) if uploaded_planning else None

    # Mappings for Task ID <-> Task Name
    task_id_to_name = dict(zip(tasks_df['id'].astype(str), tasks_df['name'].astype(str)))
    task_names = tasks_df['name'].dropna().astype(str).tolist()

    # --- SIDEBAR: PLANNING PERIOD & SETTINGS ---
    st.sidebar.header("2. Planning Period & Settings")
    st.sidebar.markdown("Choose start date and how many Sabbath services to generate (1 to 10).")
    
    start_date = st.sidebar.date_input("Start Date", value=date.today())
    num_sabbaths = st.sidebar.slider("Number of Sabbaths to Generate", min_value=1, max_value=10, value=2)

    st.sidebar.header("3. Group Rule Configuration")
    st.sidebar.markdown("Define which group takes which tasks on specific Sabbath indices of a month.")
    
    default_ss = [t for t in ["SSM", "SST", "SS5"] if t in task_names]
    default_cu = [t for t in ["SSM", "SST", "SS5", "CUM", "CUVK", "CUVP", "CUFN", "CUTA", "CUTL"] if t in task_names]

    sabbath_1_group = st.sidebar.text_input("1st Sabbath Group", value="Tanora Zokiny")
    sabbath_1_tasks = st.sidebar.multiselect("1st Sabbath Group Tasks", options=task_names, default=default_ss)

    sabbath_2_group = st.sidebar.text_input("2nd Sabbath Group", value="Zatovo")
    sabbath_2_tasks = st.sidebar.multiselect("2nd Sabbath Group Tasks", options=task_names, default=default_ss)

    sabbath_3_group = st.sidebar.text_input("3rd Sabbath Group", value="Lehibe I")
    sabbath_3_tasks = st.sidebar.multiselect("3rd Sabbath Group Tasks", options=task_names, default=default_ss)

    sabbath_4_group = st.sidebar.text_input("4th Sabbath Group", value="Lehibe II")
    sabbath_4_tasks = st.sidebar.multiselect("4th Sabbath Group Tasks", options=task_names, default=default_ss)

    sabbath_5_group = st.sidebar.text_input("5th Sabbath Group", value="MINENF")
    sabbath_5_tasks = st.sidebar.multiselect("5th Sabbath Group Tasks", options=task_names, default=default_cu)

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
    st.markdown("Uncheck any Saturday where the church is visiting another location or services are skipped.")
    
    selected_saturdays = []
    col1, col2 = st.columns(2)
    for i, sat in enumerate(all_saturdays):
        col = col1 if i % 2 == 0 else col2
        first_day_of_month = date(sat.year, sat.month, 1)
        first_sat = first_day_of_month + timedelta(days=(5 - first_day_of_month.weekday()) % 7)
        sabbath_idx = ((sat - first_sat).days // 7) + 1

        label = f"{sat.strftime('%d/%m/%Y')} (Sabbath {sabbath_idx} of {sat.strftime('%B')})"
        if col.checkbox(label, value=True, key=str(sat)):
            selected_saturdays.append((sat, sabbath_idx))

    # --- HISTORICAL ROTATION & FAIRNESS INITIALIZATION ---
    available_members = members_df[members_df['available'] == True]['name'].tolist()
    assignment_counts = {m: {t: 0 for t in task_names} for m in available_members}

    # Track who was assigned on the last scheduled Sabbath to prevent consecutive Sabbaths if possible
    last_sabbath_assigned_members = set()

    if planning_df is not None and not planning_df.empty:
        # Find the latest date in history to seed last_sabbath_assigned_members
        planning_df['parsed_date'] = pd.to_datetime(planning_df['Date'], format='%d/%m/%Y', errors='coerce')
        if not planning_df['parsed_date'].isna().all():
            max_date = planning_df['parsed_date'].max()
            last_sabbath_rows = planning_df[planning_df['parsed_date'] == max_date]
            last_sabbath_assigned_members = set(last_sabbath_rows['AssignedMember'].dropna().astype(str).str.strip())

        for _, row in planning_df.iterrows():
            m_name = str(row.get('AssignedMember', '')).strip()
            t_val = str(row.get('Task', '')).strip()
            t_name = task_id_to_name.get(t_val, t_val)
            
            if m_name in assignment_counts and t_name in assignment_counts[m_name]:
                assignment_counts[m_name][t_name] += 1

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

            # Track members already assigned on THIS specific Sabbath (Rule 1: appear once per schedule)
            assigned_on_this_sabbath = set()
            current_sabbath_assignments = set()

            for _, task in tasks_df.iterrows():
                t_id = str(task['id'])
                t_name = str(task['name'])
                
                if active_group and t_name in group_tasks:
                    assigned_person = active_group
                else:
                    # Get competent & available members
                    competent_member_ids = competencies_df[competencies_df['tasks_id'].astype(str) == t_id]['member_id'].tolist()
                    eligible = members_df[(members_df['id'].isin(competent_member_ids)) & (members_df['available'] == True)]['name'].tolist()
                    
                    if eligible:
                        # FILTER 1: Exclude members already assigned on this Sabbath (if possible)
                        not_yet_assigned = [m for m in eligible if m not in assigned_on_this_sabbath]
                        pool = not_yet_assigned if not_yet_assigned else eligible

                        # FILTER 2: Exclude members who served on the previous Sabbath (Rule 2: skip successive Sabbaths if possible)
                        rested_pool = [m for m in pool if m not in last_sabbath_assigned_members]
                        final_pool = rested_pool if rested_pool else pool

                        # FAIRNESS: Pick member with lowest historical assignment count for this task
                        eligible_counts = {m: assignment_counts.get(m, {}).get(t_name, 0) for m in final_pool}
                        min_count = min(eligible_counts.values())
                        candidates = [m for m, cnt in eligible_counts.items() if cnt == min_count]
                        
                        assigned_person = np.random.choice(candidates)
                        
                        # Record assignment tracking
                        assignment_counts[assigned_person][t_name] += 1
                        assigned_on_this_sabbath.add(assigned_person)
                        current_sabbath_assignments.add(assigned_person)
                    else:
                        assigned_person = "Unassigned"

                generated_rows.append({
                    "Date": date_str,
                    "Task": t_name,
                    "AssignedMember": assigned_person
                })
            
            # Update last Sabbath assigned members for the next loop iteration
            last_sabbath_assigned_members = current_sabbath_assignments

        result_df = pd.DataFrame(generated_rows)
        st.success("✨ Schedule successfully generated!")
        st.dataframe(result_df, use_container_width=True)

        csv_data = result_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Planning CSV",
            data=csv_data,
            file_name="Generated_Planning.csv",
            mime="text/csv",
        )
else:
    st.info("👈 Please upload your `Members.csv`, `Competencies.csv`, and `Tasks.csv` files in the sidebar to get started.")
