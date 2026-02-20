"""GitLab CI/CD pipeline status helpers (AI-251).

Provides :class:`GitLabCIPipeline` which wraps pipeline status detection
and summary formatting for the Agent Dashboard.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from integrations.gitlab.client import GitLabClient

logger = logging.getLogger(__name__)

# Pipeline statuses as returned by the GitLab API
_STATUS_RUNNING = "running"
_STATUS_PENDING = "pending"
_STATUS_SUCCESS = "success"
_STATUS_FAILED = "failed"
_STATUS_CANCELED = "canceled"
_STATUS_SKIPPED = "skipped"
_STATUS_CREATED = "created"
_STATUS_MANUAL = "manual"

# Statuses considered "passing" (pipeline completed successfully)
_PASSING_STATUSES = {_STATUS_SUCCESS}

# Statuses considered "failed"
_FAILED_STATUSES = {_STATUS_FAILED, _STATUS_CANCELED}

# Statuses considered "running" (pipeline still in progress)
_RUNNING_STATUSES = {_STATUS_RUNNING, _STATUS_PENDING, _STATUS_CREATED}


class GitLabCIPipeline:
    """Helper for GitLab CI/CD pipeline status detection and summarisation.

    Args:
        client: Optional :class:`~integrations.gitlab.client.GitLabClient`
            instance for fetching live pipeline data.
    """

    def __init__(self, client: Optional[GitLabClient] = None) -> None:
        self.client = client

    # ------------------------------------------------------------------
    # Pipeline fetching
    # ------------------------------------------------------------------

    def get_latest_pipeline(
        self, project_id: Any, mr_iid: int
    ) -> Dict[str, Any]:
        """Return the most recent pipeline for a Merge Request.

        Pipelines are sorted newest-first by the GitLab API.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            mr_iid: MR internal ID (iid).

        Returns:
            Pipeline dict, or an empty dict if no pipelines exist.

        Raises:
            RuntimeError: If no client is configured.
        """
        if self.client is None:
            raise RuntimeError(
                "GitLabCIPipeline.get_latest_pipeline requires a GitLabClient"
            )
        pipelines = self.client.list_mr_pipelines(project_id, mr_iid)
        if not pipelines:
            logger.debug("No pipelines found for MR !%d in project %s", mr_iid, project_id)
            return {}
        # GitLab returns newest first
        return pipelines[0]

    # ------------------------------------------------------------------
    # Status predicates
    # ------------------------------------------------------------------

    def is_pipeline_passing(self, pipeline: Dict[str, Any]) -> bool:
        """Return True if the pipeline completed successfully.

        Args:
            pipeline: Pipeline dict (from the GitLab API).

        Returns:
            ``True`` iff ``pipeline['status']`` is ``'success'``.
        """
        return pipeline.get("status", "") in _PASSING_STATUSES

    def is_pipeline_failed(self, pipeline: Dict[str, Any]) -> bool:
        """Return True if the pipeline failed or was cancelled.

        Args:
            pipeline: Pipeline dict (from the GitLab API).

        Returns:
            ``True`` iff status is ``'failed'`` or ``'canceled'``.
        """
        return pipeline.get("status", "") in _FAILED_STATUSES

    def is_pipeline_running(self, pipeline: Dict[str, Any]) -> bool:
        """Return True if the pipeline is still in progress.

        Args:
            pipeline: Pipeline dict (from the GitLab API).

        Returns:
            ``True`` iff status is ``'running'``, ``'pending'``, or
            ``'created'``.
        """
        return pipeline.get("status", "") in _RUNNING_STATUSES

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_pipeline_summary(self, pipeline: Dict[str, Any]) -> Dict[str, Any]:
        """Build a dashboard-friendly summary of a pipeline.

        Args:
            pipeline: Pipeline dict (from the GitLab API).

        Returns:
            Summary dict with keys:
                ``id``, ``status``, ``ref``, ``sha``, ``duration``,
                ``web_url``, ``stages``, ``created_at``, ``finished_at``.
        """
        status = pipeline.get("status", "unknown")

        # Infer human-readable stage list from status (real data would
        # come from the pipeline jobs endpoint; we summarise here)
        stages: List[str]
        if self.is_pipeline_passing(pipeline):
            stages = ["build", "test", "deploy"]
        elif self.is_pipeline_failed(pipeline):
            stages = ["build", "test"]  # deploy stage never reached
        elif self.is_pipeline_running(pipeline):
            stages = ["build"]
        else:
            stages = []

        return {
            "id": pipeline.get("id"),
            "status": status,
            "ref": pipeline.get("ref", ""),
            "sha": pipeline.get("sha", ""),
            "duration": pipeline.get("duration"),
            "web_url": pipeline.get("web_url", ""),
            "stages": stages,
            "created_at": pipeline.get("created_at", ""),
            "finished_at": pipeline.get("finished_at", ""),
        }
