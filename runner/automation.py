from pathlib import Path
import re
import subprocess
from github import Github


triggers_cohort_generation = [r"analysis/study_definition.py", r"datalab_cohorts/.*"]
triggers_model_run = [r"analysis/.*\.do"]


def filename_matches_any(list_of_rx, filename):
    for rx in list_of_rx:
        if re.match(rx, filename):
            return True
    return False


def actions_from_pull_requests():
    MAX_PULL_COUNT = 10
    g = Github("sebbacon", "22472004f1e5bf777d1b90978ee52ec49b58b078")
    repo = g.get_repo("ebmdatalab/opencorona-risk-factors-research")
    repo = g.get_repo("ebmdatalab/opencorona-research-template")
    events = repo.get_events()
    flags = []
    lastref = Path(".lastref")
    lastref.touch()
    with open(lastref, "r+") as f:
        lastref = sha = f.read()
        most_recent_ref = None
        count = 0
        for event in events:
            if event.payload.get("action") == "closed" and event.payload.get(
                "pull_request", {}
            ).get("merged"):
                needs_cohort_generation = False
                needs_model_run = False
                if event.payload["pull_request"]["base"]["ref"] == "master":
                    sha = event.payload["pull_request"]["merge_commit_sha"]
                    if most_recent_ref is None:
                        most_recent_ref = sha
                    if most_recent_ref == lastref or count > MAX_PULL_COUNT:
                        break
                    count += 1
                    cmd = ["git", "diff", "--name-only", sha + "^", sha]
                    result = subprocess.run(
                        cmd, capture_output=True, check=True, encoding="utf8"
                    )
                    for changed_file in result.stdout.splitlines():
                        if filename_matches_any(
                            triggers_cohort_generation, changed_file
                        ):
                            needs_cohort_generation = True
                        if filename_matches_any(triggers_model_run, changed_file):
                            needs_model_run = True
                flags.append((needs_cohort_generation, needs_model_run))
        f.seek(0)
        f.write(most_recent_ref)
        f.truncate()
    return (any([x[0] for x in flags]), any([x[1] for x in flags]))


def cancel_running_model():
    pass


def cancel_running_cohort():
    pass


def enqueue_model_run():
    pass


def enqueue_cohort_run():
    pass


def handle_actions():
    needs_cohort_generation, needs_model_run = actions_from_pull_requests()
    currently_running_cohort_generation = False
    currently_running_model = False
    if needs_cohort_generation and needs_model_run:
        print("cancelling and restarting everything")
    elif needs_cohort_generation and not needs_model_run:
        print("if cohort generation is running, cancel and restart")
        print("if model generation is running, let it complete???")
    elif needs_model_run and not needs_cohort_generation:
        print("if cohort generation is running, cancel and restart")
        print("????")


def deploy():
    # check out master branch to location based on ref
    pass


def generate():
    # triggers a docker generate_cohort
    pass


def run():
    # triggers a docker run
    pass


def cancel_cohort():
    # finds the docker container by id and kills it
    pass


handle_actions()

# We want to *tell* the server when to deploy
# os deploy
#  * deploys with current ref
# os list
#  * lists current deploys
# os generate <ref>
#  already running!
# os run <ref>
#  already running!
# os cancel cohort <ref>
# os cancel run <ref>
# os canel all <ref>
# os remove <ref>

# XXX handle run.exe possibly being open - everyone has their own run.exe?


# https://developer.github.com/v3/activity/events/types/#pullrequestevent
# https://pygithub.readthedocs.io/en/latest/github_objects/Event.html
