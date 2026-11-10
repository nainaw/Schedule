import streamlit as st
import pandas as pd
from utils.github_helpers import push_file_to_github
from utils.scheduling_logic import prune_planning_data, publish_public_schedule_page

def render_crud_tab(tasks_df, max_planning_rows=1000):
    st.title("📊 Data Management (Worksheet Editor)")
    dataset_choice = st.selectbox("Select Dataset to Edit", ["Members.csv", "Competencies.csv", "Tasks.csv", "Planning.csv"])
    
    from utils.github_helpers import get_github_repo_file
    content, _, _ = get_github_repo_file(dataset_choice)
    current_df = pd.read_csv(pd.io.common.StringIO(content)) if content else None

    if current_df is not None:
        display_df = current_df.copy()
        if dataset_choice == "Planning.csv" and 'Date' in display_df.columns:
            sort_direction = st.radio("Fandaminana ny Daty:", ["Recent to Old", "Old to Recent"], horizontal=True)
            display_df['__temp_date'] = pd.to_datetime(display_df['Date'], dayfirst=True, errors='coerce')
            display_df = display_df.sort_values(by='__temp_date', ascending=(sort_direction == "Old to Recent")).drop(columns=['__temp_date'])

        edited_df = st.data_editor(display_df, num_rows="dynamic", use_container_width=True, key=f"editor_{dataset_choice}")

        if st.button(f"💾 Save changes to {dataset_choice}"):
            if dataset_choice == "Planning.csv":
                edited_df = prune_planning_data(edited_df, max_rows=max_planning_rows)
            success = push_file_to_github(dataset_choice, edited_df.to_csv(index=False), f"Manual CRUD update on {dataset_choice}")
            if dataset_choice == "Planning.csv" and success:
                publish_public_schedule_page(edited_df, tasks_df)
            if success:
                st.success(f"✅ Successfully updated {dataset_choice}!")
                st.rerun()
            else:
                st.error("❌ Failed to update GitHub.")
    else:
        st.warning(f"Could not load {dataset_choice}.")