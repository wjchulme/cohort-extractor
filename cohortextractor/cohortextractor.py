#!/usr/bin/env python3

"""A cross-platform script to build cohorts, run models, build and
start a notebook, open a web browser on the correct port, and handle
shutdowns gracefully
"""
import cohortextractor
import datetime
from datetime import timedelta
import glob
import logging
import importlib
import os
import re
import requests
import shutil
import sys


import base64
from io import BytesIO
from argparse import ArgumentParser
from matplotlib import pyplot as plt
import numpy as np
from pandas.api.types import is_categorical_dtype
from pandas.api.types import is_bool_dtype
from pandas.api.types import is_datetime64_dtype
from pandas.api.types import is_numeric_dtype
from prettytable import PrettyTable
import yaml

from datetime import datetime
import seaborn as sns

from cohortextractor.remotejobs import get_branch
from cohortextractor.remotejobs import get_job_logs
from cohortextractor.remotejobs import list_workspaces
from cohortextractor.remotejobs import submit_job
from cohortextractor.remotejobs import submit_workspace
from cohortextractor.localrun import localrun

notebook_tag = "opencorona-research"
target_dir = "/home/app/notebook"


def relative_dir():
    return os.getcwd()


def make_chart(name, series, dtype):
    FLOOR_DATE = datetime(1960, 1, 1)
    CEILING_DATE = datetime.today()
    img = BytesIO()
    # Setting figure sizes in seaborn is a bit weird:
    # https://stackoverflow.com/a/23973562/559140
    if is_categorical_dtype(dtype):
        sns.set_style("ticks")
        sns.catplot(
            x=name, data=series.to_frame(), kind="count", height=3, aspect=3 / 2
        )
        plt.xticks(rotation=45)
    elif is_bool_dtype(dtype):
        sns.set_style("ticks")
        sns.catplot(x=name, data=series.to_frame(), kind="count", height=2, aspect=1)
        plt.xticks(rotation=45)
    elif is_datetime64_dtype(dtype):
        # Early dates are dummy values; I don't know what late dates
        # are but presumably just dud data
        series = series[(series > FLOOR_DATE) & (series <= CEILING_DATE)]
        # Set bin numbers appropriate to the time window
        delta = series.max() - series.min()
        if delta.days <= 31:
            bins = delta.days
        elif delta.days <= 365 * 10:
            bins = delta.days / 31
        else:
            bins = delta.days / 365
        if bins < 1:
            bins = 1
        fig = plt.figure(figsize=(5, 2))
        ax = fig.add_subplot(111)
        series.hist(bins=int(bins), ax=ax)
        plt.xticks(rotation=45, ha="right")
    elif is_numeric_dtype(dtype):
        # Trim percentiles and negatives which are usually bad data
        series = series.fillna(0)
        series = series[
            (series < np.percentile(series, 95))
            & (series > np.percentile(series, 5))
            & (series > 0)
        ]
        fig = plt.figure(figsize=(5, 2))
        ax = fig.add_subplot(111)
        sns.distplot(series, kde=False, ax=ax)
        plt.xticks(rotation=45)
    else:
        raise ValueError()

    plt.savefig(img, transparent=True, bbox_inches="tight")
    img.seek(0)
    plt.close()
    return base64.b64encode(img.read()).decode("UTF-8")


def preflight_generation_check():
    """Raise an informative error if things are not as they should be"""
    missing_paths = []
    required_paths = ["codelists/", "analysis/"]
    for p in required_paths:
        if not os.path.exists(p):
            missing_paths.append(p)
    if missing_paths:
        msg = "This command expects the following relative paths to exist: {}"
        raise RuntimeError(msg.format(", ".join(missing_paths)))


def generate_cohort(output_dir, expectations_population, selected_study_name=None):
    preflight_generation_check()
    study_definitions = list_study_definitions()
    if selected_study_name and selected_study_name != "all":
        for study_name, suffix in study_definitions:
            if study_name == selected_study_name:
                study_definitions = [(study_name, suffix)]
                break
    for study_name, suffix in study_definitions:
        print(f"Generating cohort for {study_name}...")
        _generate_cohort(output_dir, study_name, suffix, expectations_population)


def _generate_cohort(output_dir, study_name, suffix, expectations_population):
    print("Running. Please wait...")
    study = load_study_definition(study_name)

    with_sqlcmd = shutil.which("sqlcmd") is not None
    os.makedirs(output_dir, exist_ok=True)
    study.to_csv(
        f"{output_dir}/input{suffix}.csv",
        expectations_population=expectations_population,
        with_sqlcmd=with_sqlcmd,
    )
    print(
        f"Successfully created cohort and covariates at {output_dir}/input{suffix}.csv"
    )


def make_cohort_report(input_dir, output_dir):
    for study_name, suffix in list_study_definitions():
        _make_cohort_report(input_dir, output_dir, study_name, suffix)


def _make_cohort_report(input_dir, output_dir, study_name, suffix):
    study = load_study_definition(study_name)

    df = study.csv_to_df(f"{input_dir}/input{suffix}.csv")
    descriptives = df.describe(include="all")

    for name, dtype in zip(df.columns, df.dtypes):
        if name == "patient_id":
            continue
        main_chart = '<div><img src="data:image/png;base64,{}"/></div>'.format(
            make_chart(name, df[name], dtype)
        )
        empty_values_chart = ""
        if is_datetime64_dtype(dtype):
            # also do a null / not null plot
            empty_values_chart = (
                '<div><img src="data:image/png;base64,{}"/></div>'.format(
                    make_chart(name, df[name].isnull(), bool)
                )
            )
        elif is_numeric_dtype(dtype):
            # also do a null / not null plot
            empty_values_chart = (
                '<div><img src="data:image/png;base64,{}"/></div>'.format(
                    make_chart(name, df[name] > 0, bool)
                )
            )
        descriptives.loc["values", name] = main_chart
        descriptives.loc["nulls", name] = empty_values_chart

    with open(f"{output_dir}/descriptives{suffix}.html", "w") as f:

        f.write(
            """<html>
<head>
  <style>
    table {
      text-align: left;
      position: relative;
      border-collapse: collapse;
    }
    td, th {
      padding: 8px;
      margin: 2px;
    }
    td {
      border-left: solid 1px black;
    }
    tr:nth-child(even) {background: #EEE}
    tr:nth-child(odd) {background: #FFF}
    tbody th:first-child {
      position: sticky;
      left: 0px;
      background: #fff;
    }
  </style>
</head>
<body>"""
        )

        f.write(descriptives.to_html(escape=False, na_rep="", justify="left", border=0))
        f.write("</body></html>")
    print(f"Created cohort report at {output_dir}/descriptives{suffix}.html")


def update_codelists():
    base_path = os.path.join(os.getcwd(), "codelists")

    # delete all existing codelists
    for path in glob.glob(os.path.join(base_path, "*.csv")):
        os.unlink(path)

    with open(os.path.join(base_path, "codelists.txt")) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            print(line)
            project_id, codelist_id, version = line.split("/")
            url = f"https://codelists.opensafely.org/codelist/{project_id}/{codelist_id}/{version}/download.csv"

            rsp = requests.get(url)
            rsp.raise_for_status()

            with open(
                os.path.join(base_path, f"{project_id}-{codelist_id}.csv"), "w"
            ) as f:
                f.write(rsp.text)


def dump_cohort_sql(study_definition):
    study = load_study_definition(study_definition)
    print(study.to_sql())


def dump_study_yaml(study_definition):
    study = load_study_definition(study_definition)
    print(yaml.dump(study.to_data()))


def load_study_definition(name):
    sys.path.extend([relative_dir(), os.path.join(relative_dir(), "analysis")])
    # Avoid creating __pycache__ files in the analysis directory
    sys.dont_write_bytecode = True
    return importlib.import_module(name).study


def list_study_definitions():
    pattern = re.compile(r"^(study_definition(_\w+)?)\.py$")
    matches = []
    for name in sorted(os.listdir(os.path.join(relative_dir(), "analysis"))):
        match = pattern.match(name)
        if match:
            name = match.group(1)
            suffix = match.group(2) or ""
            matches.append((name, suffix))
    if not matches:
        raise RuntimeError(f"No study definitions found in {relative_dir()}")
    return matches


def main():
    parser = ArgumentParser(
        description="Generate cohorts and run models in openSAFELY framework. "
    )
    # Cohort parser options
    parser.add_argument("--version", help="Display version", action="store_true")
    parser.add_argument(
        "--verbose", help="Show extra logging info", action="store_true"
    )
    subparsers = parser.add_subparsers(help="sub-command help")
    generate_cohort_parser = subparsers.add_parser(
        "generate_cohort", help="Generate cohort"
    )
    generate_cohort_parser.set_defaults(which="generate_cohort")
    run_parser = subparsers.add_parser("run", help="Run action from project.yaml")
    run_parser.set_defaults(which="run")

    run_parser.add_argument(
        "db",
        help="Database to run against",
        choices=["full", "slice", "dummy"],
        type=str,
    )
    run_parser.add_argument(
        "action",
        help="Action to execute",
        type=str,
    )
    run_parser.add_argument(
        "backend",
        help="Backend to execute against",
        choices=["expectations", "tpp", "all"],
        type=str,
        default="all",
    )
    run_parser.add_argument(
        "--force-run",
        help="Force a new run for the action",
        action="store_true",
    )
    run_parser.add_argument(
        "--force-run-dependencies",
        help="Force a new run for the action and all its dependencies (only when `--force-run` is also specified)",
        action="store_true",
    )
    run_parser.add_argument(
        "--high-privacy-output-dir",
        help="Path for high privacy outputs",
        type=str,
        default="outputs/high_privacy",
    )
    run_parser.add_argument(
        "--medium-privacy-output-dir",
        help="Path for medium privacy outputs",
        type=str,
        default="outputs/medium_privacy",
    )
    cohort_report_parser = subparsers.add_parser(
        "cohort_report", help="Generate cohort report"
    )
    cohort_report_parser.set_defaults(which="cohort_report")
    cohort_report_parser.add_argument(
        "--input-dir",
        help="Location to look for input CSVs",
        type=str,
        default="analysis",
    )
    cohort_report_parser.add_argument(
        "--output-dir",
        help="Location to store output CSVs",
        type=str,
        default="output",
    )

    run_notebook_parser = subparsers.add_parser("notebook", help="Run notebook")
    run_notebook_parser.set_defaults(which="notebook")

    update_codelists_parser = subparsers.add_parser(
        "update_codelists",
        help="Update codelists, using specification at codelists/codelists.txt",
    )
    update_codelists_parser.set_defaults(which="update_codelists")
    dump_cohort_sql_parser = subparsers.add_parser(
        "dump_cohort_sql", help="Show SQL to generate cohort"
    )
    dump_cohort_sql_parser.add_argument(
        "--study-definition", help="Study definition name", type=str, required=True
    )
    dump_cohort_sql_parser.set_defaults(which="dump_cohort_sql")
    dump_study_yaml_parser = subparsers.add_parser(
        "dump_study_yaml", help="Show study definition as YAML"
    )
    dump_study_yaml_parser.set_defaults(which="dump_study_yaml")
    dump_study_yaml_parser.add_argument(
        "--study-definition", help="Study definition name", type=str, required=True
    )

    remote_parser = subparsers.add_parser("remote", help="Manage remote jobs")
    remote_parser.set_defaults(which="remote")

    # Remote subcommands
    remote_subparser = remote_parser.add_subparsers(help="Remote sub-command help")

    remote_run_subparser = remote_subparser.add_parser("run", help="Run an action")
    remote_run_subparser.set_defaults(which="remote_run")

    remote_workspace_subparser = remote_subparser.add_parser(
        "workspace", help="Manage workspaces"
    )
    remote_workspace_action_subparser = remote_workspace_subparser.add_subparsers(
        help="Remote workspace sub-command help"
    )
    remote_workspace_add_action_subparser = (
        remote_workspace_action_subparser.add_parser("add", help="Add a workspace")
    )
    remote_workspace_list_action_subparser = (
        remote_workspace_action_subparser.add_parser("list", help="List workspaces")
    )
    remote_workspace_add_action_subparser.set_defaults(which="workspace_add")
    remote_workspace_list_action_subparser.set_defaults(which="workspace_list")

    remote_workspace_add_action_subparser.add_argument(
        "workspace", help="id of workspace", type=str
    )
    remote_workspace_add_action_subparser.add_argument(
        "db",
        help="Database to run against",
        choices=["full", "slice", "dummy"],
        type=str,
    )

    remote_run_subparser.add_argument(
        "workspace",
        help="Workspace name",
        type=str,
    )
    remote_run_subparser.add_argument(
        "action",
        help="Action to execute",
        type=str,
    )
    remote_run_subparser.add_argument(
        "backend",
        choices=["tpp", "all"],
        type=str,
        default="all",
    )
    remote_run_subparser.add_argument(
        "--force-run",
        help="Force a new run for the action",
        action="store_true",
    )
    remote_run_subparser.add_argument(
        "--force-run-dependencies",
        help="Force a new run for the action and all its dependencies",
        action="store_true",
    )
    log_remote_parser = remote_subparser.add_parser("log", help="Show logs")
    log_remote_parser.set_defaults(which="remote_log")

    generate_cohort_parser.add_argument(
        "--output-dir",
        help="Location to store output CSVs",
        type=str,
        default="output",
    )
    generate_cohort_parser.add_argument(
        "--study-definition",
        help="Study definition to use",
        type=str,
        choices=["all"] + [x[0] for x in list_study_definitions()],
        default="all",
    )
    generate_cohort_parser.add_argument(
        "--temp-database-name",
        help="Name of database so store temporary results",
        type=str,
        default=os.environ.get("TEMP_DATABASE_NAME", ""),
    )
    cohort_method_group = generate_cohort_parser.add_mutually_exclusive_group(
        required=True
    )
    cohort_method_group.add_argument(
        "--expectations-population",
        help="Generate a dataframe from study expectations",
        type=int,
        default=0,
    )
    cohort_method_group.add_argument(
        "--database-url",
        help="Database URL to query",
        type=str,
        default=os.environ.get("DATABASE_URL", ""),
    )

    options = parser.parse_args()
    if options.force_run_dependencies and not options.force_run:
        parser.error("`--force-run-dependencies` requires `--force-run`")
    if options.version:
        print(f"v{cohortextractor.__version__}")
    elif not hasattr(options, "which"):
        parser.print_help()
    elif options.which == "run":
        options.high_privacy_output_dir = os.path.abspath(
            options.high_privacy_output_dir
        )
        options.medium_privacy_output_dir = os.path.abspath(
            options.medium_privacy_output_dir
        )
        os.makedirs(options.high_privacy_output_dir, exist_ok=True)
        os.makedirs(options.medium_privacy_output_dir, exist_ok=True)
        log_level = options.verbose and logging.INFO or logging.ERROR
        result = localrun(
            options.action,
            options.backend,
            options.db,
            options.high_privacy_output_dir,
            options.medium_privacy_output_dir,
            force_run=options.force_run,
            force_run_dependencies=options.force_run_dependencies,
            log_level=log_level,
        )
        if result:
            print("Generated outputs:")
            output = PrettyTable()
            output.field_names = ["status", "path"]

            for action in result:
                for location in action["output_locations"]:
                    location = os.path.relpath(location)
                    output.add_row(
                        [
                            action["status_message"],
                            location,
                        ]
                    )
            print(output)
        else:
            print("Nothing to do")

    elif options.which == "cohort_report":
        make_cohort_report(options.input_dir, options.output_dir)
    elif options.which == "update_codelists":
        update_codelists()
        print("Codelists updated. Don't forget to commit them to the repo")
    elif options.which == "dump_cohort_sql":
        dump_cohort_sql(options.study_definition)
    elif options.which == "dump_study_yaml":
        dump_study_yaml(options.study_definition)
    elif options.which == "workspace_add":
        workspace = submit_workspace(options.workspace, options.db)
        print(f"Workspace submitted: {workspace['url']}")
    elif options.which == "workspace_list":
        output = PrettyTable()
        output.field_names = ["id", "name"]
        for workspace in list_workspaces():
            output.add_row([workspace["id"], workspace["name"]])
        print(output)
    elif options.which == "remote_run":
        jobs = submit_job(
            options.workspace,
            options.backend,
            options.action,
            force_run=options.force_run,
            force_run_dependencies=options.force_run_dependencies,
        )
        for job in jobs:
            print(f"Job submitted to {job['backend']}: {job['url']}")
    elif options.which == "remote_log":
        output = PrettyTable()
        output.field_names = [
            "created",
            "action",
            "workspace",
            "backend",
            "status",
            "run time",
        ]
        for entry in get_job_logs():
            if not entry["started"]:
                status = "not started"
            elif entry["status_code"] is None:
                status = "running"
            elif entry["status_code"] == 0:
                status = f"finished ({len(entry['outputs'])} outputs generated)"
            else:
                status = f"error ({entry['status_code']})"
            entry["status"] = status
            created_at = datetime.fromisoformat(
                entry["created_at"].replace("Z", "+00:00")
            )
            completed_at = (
                entry["completed_at"]
                and datetime.fromisoformat(entry["completed_at"].replace("Z", "+00:00"))
                or None
            )
            if completed_at:
                elapsed = completed_at - created_at
                elapsed = timedelta(elapsed.days, elapsed.seconds)
            else:
                elapsed = None

            output.add_row(
                [
                    datetime.fromisoformat(
                        entry["created_at"].replace("Z", "+00:00")
                    ).strftime("%Y/%m/%d %H:%M"),
                    entry["operation"],
                    entry["workspace"]["name"],
                    entry["backend"],
                    status,
                    elapsed,
                ]
            )
        print(output)


if __name__ == "__main__":
    main()
