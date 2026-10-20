import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta

st.set_page_config(page_title="Church Schedule Generator", layout="wide")

st.title("⛪ Church Schedule Planning Generator")
st.markdown("Upload your datasets, customize group rules and Sabbath dates, and automatically generate the fair-rotation planning sheet.")

# --- SIDEBAR: FILE UPLOADS ---
st.sidebar.header("1. Upload CSV Files")
uploaded_members = st.sidebar.file_uploader("Members.csv", type=["csv"])
uploaded_competencies = st.sidebar.file_uploader("Competencies.csv", type=["csv"])
uploaded_tasks = st.sidebar.file_uploader("Tasks.csv", type=["csv"])
uploaded_planning = st.sidebar.file_uploader("Planning.csv (Optional for history)", type=["csv"])

if uploaded_members and uploaded_competencies and uploaded_tasks:
    members_df = pd.read_csv(uploaded_members)
    competencies_df = pd.read_csv(uploaded_competencies)
    tasks_df = pd.read_csv(uploaded_tasks)
    planning_df = pd.read_csv(uploaded_planning) if uploaded_planning else None

    # Get list of task IDs safely from Tasks.csv
    task_options = tasks_df['id'].dropna().astype(str).tolist()

    # --- SIDEBAR: DATE RANGE & CONFIG ---
    st.sidebar.header("2. Planning Period & Settings")
    st.sidebar.markdown("Set the time frame for which you want to generate the new schedule.")
    start_date = st.sidebar.date_input("Start Date", value=datetime(2026, 1, 3))
    end_date = st.sidebar.date_input("End Date", value=datetime(2026, 3, 31))

    st.sidebar.header("3. Group Rule Configuration")
    st.sidebar.markdown("Define which group takes which tasks on specific Sabbath indices of a month.")
    
    # Safe defaults checking against available task options
    default_ss = [t for t in ["SSM", "SST", "SS5"] if t in task_options]
    default_cu = [t for t in ["SSM", "SST", "SS5", "CUM", "CUVK", "CUVP", "CUFN", "CUTA", "CUTL"] if t in task_options]

    sabbath_1_group = st.sidebar.text_input("1st Sabbath Group", value="Tanora Zokiny")
    sabbath_1_tasks = st.sidebar.multiselect("1st Sabbath Group Tasks", options=task_options, default=default_ss)

    sabbath_2_group = st.sidebar.text_input("2nd Sabbath Group", value="Zatovo")
    sabbath_2_tasks = st.sidebar.multiselect("2nd Sabbath Group Tasks", options=task_options, default=default_ss)

    sabbath_3_group = st.sidebar.text_input("3rd Sabbath Group", value="Lehibe I")
    sabbath_3_tasks = st.sidebar.multiselect("3rd Sabbath Group Tasks", options=task_options, default=default_ss)

    sabbath_4_group = st.sidebar.text_input("4th Sabbath Group", value="Lehibe II")
    sabbath_4_tasks = st.sidebar.multiselect("4th Sabbath Group Tasks", options=task_options, default=default_ss)

    sabbath_5_group = st.sidebar.text_input("5th Sabbath Group", value="MINENF")
    sabbath_5_tasks = st.sidebar.multiselect("5th Sabbath Group Tasks", options=task_options, default=default_cu)

    # --- GENERATE SABBATH DATES ---
    def get_saturdays(start, end):
        cur = start + timedelta(days=(5 - start.weekday()) % 7)
        saturdays = []
        while cur <= end:
            saturdays.append(cur)
            cur += timedelta(days=7)
        return saturdays

    all_saturdays = get_saturdays(start_date, end_date)

    st.subheader("📅 Sabbath Calendar & Skipped Dates")
    st.markdown("Uncheck any Saturday where the church is visiting another location or services are cancelled.")
    
    selected_saturdays = []
    col1, col2 = st.columns(2)
    for i, sat in enumerate(all_saturdays):
        col = col1 if i % 2 == 0 else col2
        month_sats = [s for s in all_saturdays if s.year == sat.year and s.month == sat.month]
        sabbath_idx = month_sats.index(sat) + 1
        label = f"{sat.strftime('%d/%m/%Y')} (Sabbath {sabbath_idx} of {sat.strftime('%B')})"
        if col.checkbox(label, value=True, key=str(sat)):
            selected_saturdays.append((sat, sabbath_idx))

    # --- GENERATION LOGIC ---
    if st.button("🚀 Generate Schedule"):
        generated_rows = []
        assignment_counts = {row['name']: {t: 0 for t in task_options} for _, row in members_df[members_df['available'] == True].iterrows()}

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

            for _, task in tasks_df.iterrows():
                t_id = str(task['id'])
                
                if active_group and t_id in group_tasks:
                    assigned_person = active_group
                else:
                    competent_member_ids = competencies_df[competencies_df['tasks_id'].astype(str) == t_id]['member_id'].tolist()
                    eligible = members_df[(members_df['id'].isin(competent_member_ids)) & (members_df['available'] == True)]['name'].tolist()
                    
                    if eligible:
                        eligible_counts = {m: assignment_counts.get(m, {}).get(t_id, 0) for m in eligible}
                        min_count = min(eligible_counts.values())
                        candidates = [m for m, cnt in eligible_counts.items() if cnt == min_count]
                        
                        assigned_person = np.random.choice(candidates)
                        assignment_counts[assigned_person][t_id] += 1
                    else:
                        assigned_person = "Unassigned"

                generated_rows.append({
                    "Date": date_str,
                    "Task": t_id,
                    "AssignedMember": assigned_person
                })

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
