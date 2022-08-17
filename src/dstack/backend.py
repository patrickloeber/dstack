import sys
from abc import ABC
from enum import Enum
from typing import List, Optional, Generator, Tuple

from dstack.config import load_config, AwsBackendConfig
from dstack.jobs import Job, JobStatus, JobHead
from dstack.repo import RepoData, RepoCredentials
from dstack.runners import Resources, Runner
from dstack.util import _quoted


class InstanceType:
    def __init__(self, instance_name: str, resources: Resources):
        self.instance_name = instance_name
        self.resources = resources

    def __str__(self) -> str:
        return f'InstanceType(instance_name="{self.instance_name}", resources={self.resources})'.__str__()


class RequestStatus(Enum):
    RUNNING = "fullfilled"
    PENDING = "provisioning"
    TERMINATED = "terminated"
    NO_CAPACITY = "no_capacity"


class RequestHead:
    def __init__(self, job_id: str, status: RequestStatus, message: Optional[str]):
        self.job_id = job_id
        self.status = status
        self.message = message

    def __str__(self) -> str:
        return f'RequestStatus(job_id="{self.job_id}", status="{self.status.value}", ' \
               f'message="{self.message})'


class AppHead:
    def __init__(self, job_id: str, app_name: str):
        self.job_id = job_id
        self.app_name = app_name

    def __str__(self) -> str:
        return f'RunApp(job_id="{self.job_id}", app_name="{self.app_name})'


class Run:
    def __init__(self, repo_user_name: str, repo_name: str, run_name: str, workflow_name: Optional[str],
                 provider_name: str, artifacts: Optional[List[str]], status: JobStatus, submitted_at: int,
                 tag_name: Optional[str], app_heads: Optional[List[AppHead]],
                 request_heads: Optional[List[RequestHead]]):
        self.repo_user_name = repo_user_name
        self.repo_name = repo_name
        self.run_name = run_name
        self.workflow_name = workflow_name
        self.provider_name = provider_name
        self.artifacts = artifacts
        self.status = status
        self.submitted_at = submitted_at
        self.tag_name = tag_name
        self.app_heads = app_heads
        self.request_heads = request_heads

    def __str__(self) -> str:
        artifacts = ("[" + ", ".join(map(lambda a: _quoted(str(a)), self.artifacts)) + "]") if self.artifacts else None
        app_heads = ("[" + ", ".join(map(lambda a: str(a), self.app_heads)) + "]") if self.app_heads else None
        request_heads = "[" + ", ".join(
            map(lambda e: _quoted(str(e)), self.request_heads)) + "]" if self.request_heads else None
        return f'Run(repo_user_name="{self.repo_user_name}", ' \
               f'repo_name="{self.repo_name}", ' \
               f'run_name="{self.run_name}", ' \
               f'workflow_name={_quoted(self.workflow_name)}, ' \
               f'provider_name="{self.provider_name}", ' \
               f'status=JobStatus.{self.status.name}, ' \
               f'submitted_at={self.submitted_at}, ' \
               f'artifacts={artifacts}, ' \
               f'tag_name={_quoted(self.tag_name)}, ' \
               f'app_heads={app_heads}, ' \
               f'request_heads={request_heads})'


class LogEventSource(Enum):
    STDOUT = "stdout"
    STDERR = "stderr"


class LogEvent:
    def __init__(self, timestamp: int, job_id: Optional[str], log_message: str, log_source: LogEventSource):
        self.timestamp = timestamp
        self.job_id = job_id
        self.log_message = log_message
        self.log_source = log_source


class BackendError(Exception):
    def __init__(self, message: str):
        self.message = message


class TagHead:
    def __init__(self, repo_user_name: str, repo_name: str, tag_name: str, run_name: str,
                 workflow_name: Optional[str], provider_name: Optional[str], created_at: int,
                 artifacts: Optional[List[str]]):
        self.repo_user_name = repo_user_name
        self.repo_name = repo_name
        self.tag_name = tag_name
        self.run_name = run_name
        self.workflow_name = workflow_name
        self.provider_name = provider_name
        self.created_at = created_at
        self.artifacts = artifacts

    def __str__(self) -> str:
        artifacts = ("[" + ", ".join(map(lambda a: _quoted(str(a)), self.artifacts)) + "]") if self.artifacts else None
        return f'TagHead(repo_user_name="{self.repo_user_name}", ' \
               f'repo_name="{self.repo_name}", ' \
               f'tag_name="{self.tag_name}", ' \
               f'run_name="{self.run_name}", ' \
               f'workflow_name={_quoted(self.workflow_name)}, ' \
               f'provider_name="{_quoted(self.provider_name)}", ' \
               f'created_at={self.created_at}, ' \
               f'artifacts={artifacts})'


class RepoHead:
    def __init__(self, repo_user_name: str, repo_name: str, last_run_at: Optional[int], tags_count: int):
        self.repo_user_name = repo_user_name
        self.repo_name = repo_name
        self.last_run_at = last_run_at
        self.tags_count = tags_count

    def __str__(self) -> str:
        return f'RepoHead(repo_user_name="{self.repo_user_name}", ' \
               f'repo_name="{self.repo_name}", ' \
               f'last_run_at="{self.last_run_at}", ' \
               f'tags_count="{self.tags_count}")'


class Backend(ABC):
    def create_run(self, repo_user_name: str, repo_name: str) -> str:
        pass

    def submit_job(self, job: Job, counter: List[int]):
        pass

    def get_job(self, repo_user_name: str, repo_name: str, job_id: str) -> Job:
        pass

    def list_job_heads(self, repo_user_name: str, repo_name: str, run_name: Optional[str] = None) -> List[JobHead]:
        pass

    def run_job(self, job: Job) -> Runner:
        pass

    def stop_job(self, repo_user_name: str, repo_name: str, job_id: str, abort: bool):
        pass

    def delete_job_head(self, repo_user_name: str, repo_name: str, job_id: str):
        pass

    def stop_jobs(self, repo_user_name: str, repo_name: str, run_name: Optional[str], abort: bool):
        job_heads = self.list_job_heads(repo_user_name, repo_name, run_name)
        for job_head in job_heads:
            if job_head.status.is_unfinished():
                self.stop_job(repo_user_name, repo_name, job_head.job_id, abort)

    def delete_job_heads(self, repo_user_name: str, repo_name: str, run_name: Optional[str]):
        job_heads = []
        for job_head in self.list_job_heads(repo_user_name, repo_name, run_name):
            if job_head.status.is_finished():
                job_heads.append(job_head)
            else:
                if run_name:
                    sys.exit("The run is not finished yet. Stop the run first.")

        for job_head in job_heads:
            self.delete_job_head(repo_user_name, repo_name, job_head.job_id)

    def list_runs(self, repo_user_name: str, repo_name: str, run_name: Optional[str] = None,
                  include_request_heads: bool = True) -> List[Run]:
        pass

    def get_runs(self, repo_user_name: str, repo_name: str, job_heads: List[JobHead],
                 include_request_heads: bool = True) -> List[Run]:
        pass

    def poll_logs(self, repo_user_name: str, repo_name: str, run_name: str, start_time: int,
                  attached: bool) -> Generator[LogEvent, None, None]:
        pass

    def download_run_artifact_files(self, repo_user_name: str, repo_name: str, run_name: str,
                                    output_dir: Optional[str]):
        pass

    def list_run_artifact_files(self, repo_user_name: str, repo_name: str, run_name: str) -> List[Tuple[str, str, int]]:
        pass

    def list_tag_heads(self, repo_user_name: str, repo_name: str) -> List[TagHead]:
        pass

    def get_tag_head(self, repo_user_name: str, repo_name: str, tag_name: str) -> Optional[TagHead]:
        pass

    def create_tag_from_run(self, repo_user_name: str, repo_name: str, tag_name: str, run_name: str):
        pass

    def create_tag_from_local_dirs(self, repo_data: RepoData, tag_name: str, local_dirs: List[str]):
        pass

    def delete_tag(self, repo_user_name: str, repo_name: str, tag_head: TagHead):
        pass

    def list_repo_heads(self) -> List[RepoHead]:
        pass

    def update_repo_last_run_at(self, repo_user_name: str, repo_name: str, last_run_at: int):
        pass

    def increment_repo_tags_count(self, repo_user_name: str, repo_name: str):
        pass

    def decrement_repo_tags_count(self, repo_user_name: str, repo_name: str):
        pass

    def save_repo_credentials(self, repo_user_name: str, repo_name: str, repo_credentials: RepoCredentials):
        pass


def load_backend() -> Backend:
    config = load_config()
    if isinstance(config.backend_config, AwsBackendConfig):
        from dstack.aws import AwsBackend

        return AwsBackend(config.backend_config)
    else:
        raise Exception(f"Unsupported backend: {config.backend_config}")
