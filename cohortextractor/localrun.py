import logging
import os
from jobrunner.job import Job
from cohortextractor.remotejobs import get_repo, get_branch


def localrun(
    operation,
    backend,
    db,
    high_privacy_storage_base,
    medium_privacy_storage_base,
    force_run=False,
    force_run_dependencies=False,
):
    repo = get_repo()
    job_spec = {
        "url": "",
        "backend": backend,
        "run_locally": True,
        "operation": operation,
        "force_run": force_run,
        "force_run_dependencies": force_run_dependencies,
        "workspace": {
            "id": 1,
            "url": "",
            "name": "local",
            "repo": repo,
            "branch": get_branch(),
            "db": db,
            "owner": "me",
        },
        "workspace_id": 1,
    }

    os.environ["HIGH_PRIVACY_STORAGE_BASE"] = high_privacy_storage_base
    os.environ["MEDIUM_PRIVACY_STORAGE_BASE"] = medium_privacy_storage_base
    job = Job(job_spec, workdir=os.getcwd())
    # job.logger.setLevel(logging.WARNING)
    return job.main()
