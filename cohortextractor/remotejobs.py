from tinynetrc import Netrc
from urllib.parse import urlparse
import getpass
import os
import requests
import subprocess

JOB_SERVER = "https://jobs.opensafely.org"
JOB_ENDPOINT = f"{JOB_SERVER}/jobs/"
WORKSPACE_ENDPOINT = f"{JOB_SERVER}/workspaces/"


def set_auth():
    """Set HTTP auth (used by `requests`)"""
    # In due course, we should use Github OAuth for this
    netrc_path = os.path.join(os.path.expanduser("~"), ".netrc")
    if not os.path.exists(netrc_path):
        with open(netrc_path, "w") as f:
            f.write("")
    netrc = Netrc()
    hostname = urlparse(JOB_SERVER).hostname
    if netrc[hostname]["password"]:
        login = netrc[hostname]["login"]
        password = netrc[hostname]["password"]
    else:
        login = input("Job server username: ")
        password = getpass.getpass(
            "Password (warning: Ctrl+V won't work here; try Ctrl+Shift+V if you want to paste): "
        )
        netrc[hostname] = {"login": login, "password": password}
        netrc.save()
    return (login, password)


def get_branch():
    cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
    return subprocess.check_output(cmd, encoding="utf8").strip()


def get_repo():
    cmd = ["git", "config", "--get", "remote.origin.url"]
    result = subprocess.check_output(cmd, encoding="utf8").strip()
    if result.startswith("git@github.com"):
        # Turn git@github.com:opensafely/cohort-extractor.git into
        # https://github.com/opensafely/cohort-extractor
        org_and_repo = result.split(":")[1]
        result = f"https://github.com/{org_and_repo}"
    if result.endswith(".git"):
        result = result[: -len(".git")]
    return result


def get_job_logs():
    set_auth()
    data = {"repo": get_repo()}
    response = requests.get(JOB_ENDPOINT, params=data)
    response.raise_for_status()
    return response.json()["results"]


def do_request(url, method_name, data):
    set_auth()
    if method_name == "get":
        response = requests.get(url, params=data)
    elif method_name == "post":
        response = requests.post(url, json=data)
    response.raise_for_status()
    return response.json()


def do_get(url, data):
    return do_request(url, "get", data)


def do_post(url, data):
    return do_request(url, "post", data)


def submit_workspace(workspace_id, db):
    workspace = {
        "name": workspace_id,
        "repo": get_repo(),
        "branch": get_branch(),
        "db": db,
        "owner": getpass.getuser(),
    }
    return do_post(WORKSPACE_ENDPOINT, workspace)


def list_workspaces():
    return do_get(WORKSPACE_ENDPOINT, {"owner": getpass.getuser()})["results"]


def submit_job(
    workspace_id, backend, action, force_run=False, force_run_dependencies=False
):
    allowed_backends = ["all", "tpp"]
    if backend == "all":
        backends = allowed_backends[:]
        backends.remove("all")
    else:
        backends = [backend]
    existing_workspace = do_get(WORKSPACE_ENDPOINT, {"id": workspace_id})["results"]
    assert existing_workspace, "No matching workspace found"
    responses = []
    for backend in backends:
        data = {
            "force_run": force_run,
            "force_run_dependencies": force_run_dependencies,
            "operation": action,
            "workspace_id": existing_workspace[0]["id"],
        }
        callback_url = os.environ.get("EBMBOT_CALLBACK_URL", "")
        if callback_url:
            data["callback_url"] = callback_url
        responses.append(do_post(JOB_ENDPOINT, data))
    return responses
