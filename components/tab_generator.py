import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from utils.github_helpers import push_file_to_github
from utils.scheduling_logic import (
    prune_planning_data, 
    get_member_task_staleness, 
    is_member_held_for_older_task, 
    publish_public_schedule_page
)

def render_generator_tab(members_df, competencies_df, tasks_df, planning_df, config_data):
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

    # Sidebar inputs passed or managed globally
    start_date = config_data.get("start_date", date.today())
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    num_sabbaths = config_data.get("num_sabbaths", 2)
    max_planning_rows = config_data.get("max_planning_rows", 1000)
    elder_sabbath_choice = config_data.get("elder_sabbath_choice", 2)

    s1 = config_data.get("s1", {"group": "Tanora Zokiny", "tasks": []})
    s2 = config_data.get("s2", {"group": "Zatovo", "tasks": []})
    s3 = config_data.get("s3", {"group": "Lehibe I", "tasks": []})
    s4 = config_data.get("s4", {"group": "Lehibe II", "tasks": []})
    s5 = config_data.get("s5", {"group": "MINENF", "tasks": []})

    task_names = [str(x).strip() for x in tasks_df['name'].dropna().tolist() if str(x).strip()]
    task_name_to_id = {str(r['name']).strip(): str(r['id']).strip() for _, r in tasks_df.iterrows()}
    task_id_to_name = {str(r['id']).strip(): str(r['name']).strip() for _, r in tasks_df.iterrows()}

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

    def clean_s(val):
        return str(val).strip() if pd.notna(val) else ""

    available_members = [clean_s(m) for m in members_df[members_df['available'] == True]['name'].tolist()]
    last_performed_date = {m: {} for m in available_members}
    member_last_service_date = {}

    existing_dates = set()
    if planning_df is not None and not planning_df.empty:
        planning_df['parsed_date'] = pd.to_datetime(planning_df['Date'], dayfirst=True, errors='coerce')
        planning_df['CleanMember'] = planning_df['AssignedMember'].astype(str).str.strip()
        planning_df['CleanTask'] = planning_df['Task'].astype(str).str.strip()
        planning_df['NormalizedTask'] = planning_df['CleanTask'].apply(lambda x: task_id_to_name.get(x, x))
        existing_dates = set(planning_df['parsed_date'].dt.date.dropna())

        for _, row in planning_df.iterrows():
            m_name = str(row.get('CleanMember', '')).strip()
            t_val = str(row.get('CleanTask', '')).strip()
            t_name = task_id_to_name.get(t_val, t_val)
            p_date_raw = row.get('parsed_date')
            
            if m_name in available_members and pd.notna(p_date_raw):
                p_date = pd.to_datetime(p_date_raw).date()
                current_latest = last_performed_date[m_name].get(t_name)
                if current_latest is None or p_date > current_latest:
                    last_performed_date[m_name][t_name] = p_date
                
                global_latest = member_last_service_date.get(m_name)
                if global_latest is None or p_date > global_latest:
                    member_last_service_date[m_name] = p_date

    if st.button("🚀 Generate Schedule"):
        valid_saturdays = []
        skipped_dates = []
        
        for sat, s_idx in selected_saturdays:
            if sat in existing_dates:
                skipped_dates.append(sat.strftime('%d/%m/%Y'))
            else:
                valid_saturdays.append((sat, s_idx))

        if skipped_dates:
            st.warning(f"⚠️ Notice: Schedule generation skipped for dates that already exist: **{', '.join(skipped_dates)}**")

        if not valid_saturdays:
            st.info("ℹ️ All selected Sabbath dates already exist in your Planning history.")
        else:
            generated_rows = []
            valid_saturdays.sort(key=lambda x: x[0])

            for sat, s_idx in valid_saturdays:
                date_str = sat.strftime('%d/%m/%Y')
                
                active_group = None
                group_tasks = []
                if s_idx == 1:
                    active_group, group_tasks = s1["group"], s1["tasks"]
                elif s_idx == 2:
                    active_group, group_tasks = s2["group"], s2["tasks"]
                elif s_idx == 3:
                    active_group, group_tasks = s3["group"], s3["tasks"]
                elif s_idx == 4:
                    active_group, group_tasks = s4["group"], s4["tasks"]
                elif s_idx == 5:
                    active_group, group_tasks = s5["group"], s5["tasks"]

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
                sabbath_schedule = {}

                current_planning_history_df = planning_df.copy() if planning_df is not None else pd.DataFrame(columns=["Date", "Task", "AssignedMember", "parsed_date", "CleanMember", "CleanTask", "NormalizedTask"])

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

                            rested_pool = []
                            for m in pool:
                                last_serv_date = member_last_service_date.get(m)
                                if last_serv_date is None or (sat - last_serv_date).days >= 13:
                                    rested_pool.append(m)

                            final_pool = rested_pool if rested_pool else pool

                            member_last_dates = {
                                m: get_member_task_staleness(m, t_name, current_planning_history_df, date_str)
                                for m in final_pool
                            }
                            
                            sorted_candidates = sorted(final_pool, key=lambda m: member_last_dates[m])
                            
                            chosen_person = None
                            non_held_candidates = [
                                c for c in sorted_candidates 
                                if not is_member_held_for_older_task(c, t_name, task_names, current_planning_history_df, date_str, competencies_df, members_df, task_name_to_id)
                            ]
                            
                            if non_held_candidates:
                                chosen_person = non_held_candidates[0]
                            else:
                                chosen_person = sorted_candidates[0]
                                
                            assigned_person = chosen_person
                            
                            last_performed_date[assigned_person][t_name] = sat
                            member_last_service_date[assigned_person] = sat
                            assigned_on_this_sabbath.add(assigned_person)
                            
                            new_row_temp = pd.DataFrame([{
                                "Date": date_str, "Task": t_name, "AssignedMember": assigned_person,
                                "parsed_date": pd.to_datetime(date_str, format="%d/%m/%Y"),
                                "CleanMember": assigned_person, "CleanTask": t_name, "NormalizedTask": t_name
                            }])
                            current_planning_history_df = pd.concat([current_planning_history_df, new_row_temp], ignore_index=True)
                        else:
                            assigned_person = "Unassigned"

                    sabbath_schedule[t_name] = assigned_person

                for _, task in tasks_df.iterrows():
                    t_name = clean_s(task['name'])
                    generated_rows.append({
                        "Date": date_str, "Task": t_name, "AssignedMember": sabbath_schedule.get(t_name, "Unassigned")
                    })

            result_df = pd.DataFrame(generated_rows)
            st.success("✨ Schedule successfully generated!")
            st.dataframe(result_df, use_container_width=True)

            with st.spinner("Updating Planning.csv and publishing web page..."):
                base_planning_df = planning_df.drop(columns=['parsed_date', 'CleanMember', 'CleanTask', 'NormalizedTask'], errors='ignore') if planning_df is not None and not planning_df.empty else pd.DataFrame(columns=["Date", "Task", "AssignedMember"])
                updated_planning_df = pd.concat([base_planning_df, result_df], ignore_index=True)
                updated_planning_df = prune_planning_data(updated_planning_df, max_rows=max_planning_rows)
                
                success_csv = push_file_to_github("Planning.csv", updated_planning_df.to_csv(index=False), "Auto-update & prune Planning.csv")
                publish_public_schedule_page(updated_planning_df, tasks_df, num_latest=num_sabbaths)

                if success_csv:
                    st.balloons()
                    st.success("🎉 Successfully updated Planning.csv and public webpage!")
                else:
                    st.warning("⚠️ Auto-commit failed, check token permissions.")