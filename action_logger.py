import datetime

import subprocess
from argparse import ArgumentParser
from time import sleep

from github import Github

ACTION_LOG = "action.log"
REPO = "ebmdatalab/opencorona-research-template"

FORMAT_STRING = "{commit}	{timestamp}	{begin_or_end}	{operation}\n"
ACCESS_TOKEN = "49858f21380860e59446db84e5a9b5df85f38a11"


def log(commit, begin_or_end, operation):
    timestamp = datetime.datetime.now().isoformat()
    with open(ACTION_LOG, "a+") as f:
        f.write(
            FORMAT_STRING.format(
                commit=commit,
                timestamp=timestamp,
                begin_or_end=begin_or_end,
                operation=operation,
            )
        )
    # XXX assert on a clean master branch
    subprocess.run(["git", "checkout", "-q", "master"], check=True)
    subprocess.run(["git", "pull"], check=True)
    subprocess.run(["git", "add", ACTION_LOG], check=True)
    subprocess.run(["git", "commit", ACTION_LOG, "-m", "Logger automation"], check=True)
    subprocess.run(["git", "push", "-q", "origin", "master"], check=True)


def wait_for(commit, begin_or_end, operation):
    g = Github(ACCESS_TOKEN)
    repo = g.get_repo(REPO)
    while True:
        action_log = repo.get_contents(ACTION_LOG).decoded_content.decode("utf8")
        for line in action_log.split("\n"):
            if not line:
                continue
            this_commit, this_timestamp, this_begin_or_end, this_operation = line.strip().split(
                "\t"
            )
            if (
                this_commit == commit
                and this_begin_or_end == begin_or_end
                and this_operation == operation
            ):
                return
        sleep(1)


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "action", help="What to do", choices=["log", "wait_for"], type=str
    )
    parser.add_argument(
        "--commit",
        help="Commit hash (or other string unique to this deployment)",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--operation", help="The operation to log", type=str, required=True
    )
    parser.add_argument(
        "--begin-or-end",
        help="Type of timestamp",
        choices=["BEGIN", "END"],
        type=str,
        required=True,
    )
    options = parser.parse_args()
    if options.action == "log":
        log(options.commit, options.begin_or_end, options.operation)
    else:
        wait_for(options.commit, options.begin_or_end, options.operation)


if __name__ == "__main__":
    main()
