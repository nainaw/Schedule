import base64
import json
import requests
import streamlit as st

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