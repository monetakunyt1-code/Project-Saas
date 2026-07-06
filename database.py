from docurapi.db.connection import connect, initialize_database, utc_now
from docurapi.db.jobs_repository import (
    clear_job_history,
    complete_job,
    create_job,
    delete_job,
    fail_job,
    get_job,
    list_jobs,
    mark_job_paid,
    remove_job_files,
)
from docurapi.db.templates_repository import (
    delete_template,
    get_template,
    list_templates,
    register_template,
    remove_template_file,
)

__all__ = [
    "connect",
    "initialize_database",
    "utc_now",
    "create_job",
    "complete_job",
    "fail_job",
    "mark_job_paid",
    "get_job",
    "list_jobs",
    "delete_job",
    "clear_job_history",
    "remove_job_files",
    "register_template",
    "list_templates",
    "get_template",
    "delete_template",
    "remove_template_file",
]
