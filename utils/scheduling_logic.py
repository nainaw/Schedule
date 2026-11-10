import pandas as pd
from datetime import datetime, date
from utils.github_helpers import push_file_to_github

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

def get_member_task_staleness(member, task_name, h_df, target_date_str):
    """Returns the date when 'member' last performed 'task_name'. Returns 1900-01-01 if never."""
    if h_df is None or h_df.empty:
        return datetime(1900, 1, 1)
    
    target_dt = datetime.strptime(target_date_str, "%d/%m/%Y")
    m_clean = member.strip().upper()
    t_clean = task_name.strip().upper()
    
    cm_col = h_df['CleanMember'] if 'CleanMember' in h_df.columns else h_df['AssignedMember'].astype(str).str.strip()
    ct_col = h_df['CleanTask'] if 'CleanTask' in h_df.columns else h_df['Task'].astype(str).str.strip()
    nt_col = h_df['NormalizedTask'] if 'NormalizedTask' in h_df.columns else ct_col
    date_col = h_df['parsed_date'] if 'parsed_date' in h_df.columns else pd.to_datetime(h_df['Date'], dayfirst=True, errors='coerce')

    task_sub = h_df[
        (cm_col.str.upper() == m_clean) & 
        (
            (ct_col.str.upper() == t_clean) | 
            (nt_col.str.upper() == t_clean)
        ) &
        (date_col < target_dt)
    ]
    if task_sub.empty:
        return datetime(1900, 1, 1)
    
    valid_dates = pd.to_datetime(task_sub['Date'], dayfirst=True, errors='coerce').dropna()
    if valid_dates.empty:
        return datetime(1900, 1, 1)
        
    return valid_dates.max().to_pydatetime()

def is_member_held_for_older_task(member, current_task, all_tasks, h_df, target_date_str, comp_df, mem_df, task_name_to_id):
    """Strictly checks if 'member' has another task that is severely neglected (>90 days overdue)."""
    current_task_last_dt = get_member_task_staleness(member, current_task, h_df, target_date_str)
    target_dt = datetime.strptime(target_date_str, "%d/%m/%Y")
    
    for other_task in all_tasks:
        if other_task == current_task:
            continue
        
        t_id_other = task_name_to_id.get(other_task, "")
        comp_ids = comp_df[comp_df['tasks_id'].astype(str).str.strip() == t_id_other]['member_id'].tolist()
        member_row = mem_df[mem_df['name'].str.strip().str.upper() == member.strip().upper()]
        
        if not member_row.empty and member_row['id'].iloc[0] in comp_ids:
            other_task_last_dt = get_member_task_staleness(member, other_task, h_df, target_date_str)
            
            if other_task_last_dt == datetime(1900, 1, 1):
                return True
                
            days_since_other = (target_dt - other_task_last_dt).days
            days_since_current = (target_dt - current_task_last_dt).days if current_task_last_dt != datetime(1900, 1, 1) else 9999
            
            if days_since_other > days_since_current + 90:
                return True
                
    return False

def publish_public_schedule_page(planning_df, tasks_df, num_latest=3):
    """Publishes index.html with a checkbox toggle for Card vs Table view, forcing table view on print."""
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
    df['CleanMember'] = df['AssignedMember'].astype(str).str.strip()
    
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
    latest_dates_slice = sorted(list(set(latest_dates_slice)))

    filtered_plan = valid_plan[valid_plan['parsed_date'].dt.date.isin(latest_dates_slice)].copy()
    
    if ordered_task_names:
        task_cat = pd.CategoricalDtype(categories=ordered_task_names, ordered=True)
        filtered_plan['TaskOrder'] = filtered_plan['CleanTask'].astype(task_cat)
        filtered_plan = filtered_plan.sort_values(by='TaskOrder')

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
                <span class="member-name">{str(row['CleanMember']).strip()}</span>
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

    date_cols_str = [d.strftime('%d/%m/%Y') for d in latest_dates_slice]
    pivot_table = filtered_plan.pivot_table(index='CleanTask', columns='Date', values='CleanMember', aggfunc='first')
    
    if ordered_task_names:
        existing_tasks = [t for t in ordered_task_names if t in pivot_table.index]
        pivot_table = pivot_table.reindex(existing_tasks)

    existing_date_cols = [c for c in date_cols_str if c in pivot_table.columns]
    pivot_table = pivot_table[existing_date_cols]

    th_html = "<th>Fanompoana (Task)</th>"
    for d_str in existing_date_cols:
        th_html += f"<th>{d_str}</th>"

    tr_html = ""
    for task_code, row_data in pivot_table.iterrows():
        t_display = task_desc_map.get(task_code, task_code)
        tr_html += f"<tr><td class='task-cell'><strong>{task_code}</strong><br><span style='font-size:9px; color:#555;'>{t_display}</span></td>"
        for d_str in existing_date_cols:
            member_val = row_data.get(d_str, "-")
            if pd.isna(member_val):
                member_val = "-"
            tr_html += f"<td>{member_val}</td>"
        tr_html += "</tr>"

    html_content = f"""<!DOCTYPE html>
<html lang="mg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anjara Fanompoana Isan-Tsabata</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #2c3e50; }}
        .container {{ max-width: 850px; margin: auto; }}
        .main-title {{ text-align: center; color: #1a252f; font-size: 24px; font-weight: 800; margin-bottom: 20px; text-transform: uppercase; }}
        .controls-bar {{ display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 30px; }}
        .btn-print {{ background-color: #2c3e50; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; }}
        .sabbath-card {{ background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 30px; border: 1px solid #e1e8ed; }}
        .card-date-header {{ background-color: #ffffff; color: #2980b9; padding: 16px; text-align: center; font-size: 18px; font-weight: 700; border-bottom: 2px solid #edf2f7; }}
        .card-body {{ padding: 0 20px 10px 20px; }}
        .schedule-row {{ display: flex; justify-content: space-between; align-items: center; padding: 14px 0; border-bottom: 1px solid #f1f5f9; }}
        .task-name {{ color: #7f8c8d; font-size: 14px; font-weight: 500; flex: 1; }}
        .member-name {{ color: #1a252f; font-size: 15px; font-weight: 700; text-align: right; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th, td {{ border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }}
        th {{ background-color: #f1f5f9; color: #1e293b; font-weight: 700; text-align: center; }}
        .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #95a5a6; }}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="main-title">Anjara Fanompoana Isan-Tsabata</h1>
        <div class="web-cards-view">{sabbath_cards_html}</div>
    </div>
</body>
</html>
"""
    push_file_to_github("index.html", html_content, "Auto-publish index.html")