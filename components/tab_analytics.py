import streamlit as st
import pandas as pd
from datetime import date

def render_analytics_tab(members_df, competencies_df, tasks_df, planning_df):
    st.title("🔍 Rotation Analytics & Query")
    st.markdown("Query historical assignments and member rotation history.")

    def clean_s(val):
        return str(val).strip() if pd.notna(val) else ""

    task_names = [clean_s(x) for x in tasks_df['name'].dropna().tolist() if clean_s(x)]
    task_name_to_id = {clean_s(r['name']): clean_s(r['id']) for _, r in tasks_df.iterrows()}

    def get_member_task_history_info(p_df, member_name, task_name):
        if p_df is None or p_df.empty:
            return None, "Never"
        m_upper, t_upper = member_name.strip().upper(), task_name.strip().upper()
        t_id = task_name_to_id.get(task_name, "").upper()
        
        task_sub = p_df[
            (p_df['CleanMember'].str.upper() == m_upper) &
            ((p_df['CleanTask'].str.upper() == t_upper) | (p_df['CleanTask'].str.upper() == t_id) | (p_df['NormalizedTask'].str.upper() == t_upper))
        ].dropna(subset=['parsed_date'])
        
        if not task_sub.empty:
            max_d = task_sub['parsed_date'].max().date()
            return max_d, max_d.strftime('%d/%m/%Y')
        return None, "Never"

    if planning_df is not None and not planning_df.empty:
        valid_p_df = planning_df.dropna(subset=['parsed_date']).sort_values(by='parsed_date', ascending=False)
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("📋 Task History")
            sel_task_query = st.selectbox("Select Fanompoana (Task)", options=task_names, key="query_task_sel")
            t_id_q = task_name_to_id.get(sel_task_query, "")
            comp_m_ids = competencies_df[competencies_df['tasks_id'].astype(str).str.strip() == t_id_q]['member_id'].tolist() if t_id_q else []
            comp_members = [clean_s(m) for m in members_df[members_df['id'].isin(comp_m_ids)]['name'].tolist()] if comp_m_ids else [clean_s(m) for m in members_df['name'].tolist()]
            
            query_rows = []
            default_p_date = date(2000, 1, 1)
            for m in comp_members:
                last_d, d_display = get_member_task_history_info(valid_p_df, m, sel_task_query)
                query_rows.append({"Anarana (Member)": m, "Daty farany (Last Date)": d_display, "_sort": last_d if last_d else default_p_date})
            
            query_result_df = pd.DataFrame(query_rows).sort_values(by="_sort", ascending=True).drop(columns=['_sort'])
            st.dataframe(query_result_df, use_container_width=True, hide_index=True)
        
        with col_right:
            st.subheader("👤 Member History")
            all_m_names = sorted([clean_s(m) for m in members_df['name'].dropna().unique().tolist()]) if members_df is not None else []
            sel_member_query = st.selectbox("Select Anarana (Member)", options=all_m_names, key="query_member_sel")
            m_history_df = valid_p_df[valid_p_df['CleanMember'].str.upper() == sel_member_query.upper()]
            
            if not m_history_df.empty:
                st.dataframe(m_history_df[['Date', 'Task']].rename(columns={'Date': 'Daty (Date)', 'Task': 'Andraikitra (Task)'}), use_container_width=True, hide_index=True)
            else:
                st.info(f"No records found for {sel_member_query}.")
    else:
        st.info("No planning history available.")