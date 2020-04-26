import datetime
import os

from argparse import ArgumentParser
from time import sleep

from github import Github

ACTION_LOG = "action.log"
REPO = "ebmdatalab/opencorona-research-template"

FORMAT_STRING = "{commit}	{timestamp}	{begin_or_end}	{operation}\n"
ACCESS_TOKEN = os.environ["GITHUB_READ_PRIVATE_REPO_TOKEN"]


def get_repo():
    g = Github(ACCESS_TOKEN)
    return g.get_repo(REPO)


def get_log_file():
    return get_repo().get_contents(ACTION_LOG)


def log(commit, begin_or_end, operation):
    timestamp = datetime.datetime.now().isoformat()
    message = FORMAT_STRING.format(
        commit=commit,
        timestamp=timestamp,
        begin_or_end=begin_or_end,
        operation=operation,
    )
    log_file = get_log_file()
    existing = log_file.decoded_content.decode("utf8")
    existing += message
    get_repo().update_file(
        ACTION_LOG, message="Automatic logger", content=existing, sha=log_file.sha
    )


def wait_for(commit, begin_or_end, operation):
    while True:
        action_log = get_log_file().decoded_content.decode("utf8")
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
        sleep(5)


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
