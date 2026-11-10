import streamlit as st
import pandas as pd
from datetime import date

def render_view_tab(planning_df, tasks_df):
    st.title("👥 Member Schedule View")
    if planning_df is not None and not planning_df.empty:
        valid_plan = planning_df.dropna(subset=['parsed_date']).sort_values(by='parsed_date')
        unique_dates = valid_plan['parsed_date'].dt.date.unique()

        if len(unique_dates) > 0:
            num_latest_to_show = st.slider("Number of latest Sabbath batches to display", 1, 5, 3)
            latest_dates_slice = sorted(list(set(list(unique_dates[-num_latest_to_show:]) + [unique_dates[-1]])))
            filtered_plan = valid_plan[valid_plan['parsed_date'].dt.date.isin(latest_dates_slice)].copy()
            
            task_names = [str(x).strip() for x in tasks_df['name'].dropna().tolist()] if tasks_df is not None else []
            if task_names:
                filtered_plan['TaskOrder'] = filtered_plan['NormalizedTask'].astype(pd.CategoricalDtype(categories=task_names, ordered=True))
                filtered_plan = filtered_plan.sort_values(by='TaskOrder')

            pivot_df = filtered_plan.pivot(index='Task', columns='Date', values='AssignedMember')
            st.dataframe(pivot_df, use_container_width=True)
        else:
            st.info("No valid dated records found.")
    else:
        st.info("Planning history is empty.")