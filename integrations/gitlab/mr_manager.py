"""GitLab Merge Request manager (AI-251).

Higher-level workflow logic built on top of :class:`GitLabClient`.
Handles branch naming, MR creation, pipeline gating, and merge.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from integrations.gitlab.client import GitLabClient
from integrations.gitlab.ci_pipeline import GitLabCIPipeline

logger = logging.getLogger(__name__)

# Default polling interval (seconds) when waiting for pipeline completion
_POLL_INTERVAL = 10


class GitLabMRManager:
    """High-level manager for GitLab branch/MR/pipeline workflows.

    Args:
        client: :class:`~integrations.gitlab.client.GitLabClient` instance.
        pipeline: Optional :class:`~integrations.gitlab.ci_pipeline.GitLabCIPipeline`
            instance.  If omitted, one is created automatically.
    """

    def __init__(
        self,
        client: GitLabClient,
        pipeline: Optional[GitLabCIPipeline] = None,
    ) -> None:
        self.client = client
        self.pipeline = pipeline or GitLabCIPipeline(client=client)

    # ------------------------------------------------------------------
    # Branch helpers
    # ------------------------------------------------------------------

    def create_feature_branch(
        self, project_id: Any, issue_key: str, base_branch: str = "main"
    ) -> str:
        """Create a feature branch derived from an issue key.

        Branch names are normalised to lowercase with hyphens replacing
        non-alphanumeric characters, prefixed with ``feature/``.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            issue_key: Issue key used to generate the branch name,
                e.g. ``'AI-251'``.
            base_branch: The branch to create from (default: ``'main'``).

        Returns:
            The created branch name (e.g. ``'feature/ai-251'``).

        Raises:
            GitLabClientError: On API error.
        """
        # Normalise: lowercase, replace non-alphanumeric with hyphens, strip
        safe = re.sub(r"[^a-zA-Z0-9]+", "-", issue_key).strip("-").lower()
        branch_name = f"feature/{safe}"
        logger.info(
            "Creating feature branch %s from %s in project %s",
            branch_name, base_branch, project_id,
        )
        self.client.create_branch(project_id, branch_name, ref=base_branch)
        return branch_name

    # ------------------------------------------------------------------
    # MR creation
    # ------------------------------------------------------------------

    def create_agent_mr(
        self,
        project_id: Any,
        branch: str,
        title: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a Merge Request for an agent-generated branch.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            branch: Source branch (feature branch).
            title: MR title.
            description: MR description (Markdown).
            labels: Optional list of label names.

        Returns:
            MR dict as returned by the GitLab API.

        Raises:
            GitLabClientError: On API error.
        """
        logger.info("Creating agent MR '%s' from branch %s", title, branch)
        return self.client.create_merge_request(
            project_id=project_id,
            source_branch=branch,
            target_branch="main",
            title=title,
            description=description,
            labels=labels,
        )

    # ------------------------------------------------------------------
    # Pipeline gating
    # ------------------------------------------------------------------

    def wait_for_pipeline(
        self,
        project_id: Any,
        mr_iid: int,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Poll pipeline status until it completes or times out.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            mr_iid: MR internal ID (iid).
            timeout: Maximum seconds to wait (default: ``300``).

        Returns:
            The final pipeline dict (may still be running if timeout hit).
        """
        deadline = time.time() + timeout
        last_pipeline: Dict[str, Any] = {}

        while time.time() < deadline:
            try:
                pipeline = self.pipeline.get_latest_pipeline(project_id, mr_iid)
            except Exception as exc:
                logger.warning("Error fetching pipeline status: %s", exc)
                time.sleep(_POLL_INTERVAL)
                continue

            if not pipeline:
                logger.debug("No pipeline yet for MR !%d, waiting...", mr_iid)
                time.sleep(_POLL_INTERVAL)
                continue

            last_pipeline = pipeline
            status = pipeline.get("status", "")
            logger.debug("Pipeline status for MR !%d: %s", mr_iid, status)

            if not self.pipeline.is_pipeline_running(pipeline):
                # Pipeline has reached a terminal state
                return pipeline

            time.sleep(_POLL_INTERVAL)

        logger.warning(
            "Pipeline wait timed out after %ds for MR !%d in project %s",
            timeout, mr_iid, project_id,
        )
        return last_pipeline

    # ------------------------------------------------------------------
    # Merge readiness
    # ------------------------------------------------------------------

    def can_merge(self, project_id: Any, mr_iid: int) -> bool:
        """Check whether an MR is safe to merge.

        An MR is safe to merge when:
        - Its latest pipeline is passing (or no pipeline exists)
        - The MR state is ``'opened'`` (not already merged/closed)
        - There are no merge conflicts (``merge_status == 'can_be_merged'``)

        Args:
            project_id: GitLab project ID or URL-encoded path.
            mr_iid: MR internal ID (iid).

        Returns:
            ``True`` if the MR can be merged, ``False`` otherwise.
        """
        try:
            mr = self.client.get_mr(project_id, mr_iid)
        except Exception as exc:
            logger.error("Failed to fetch MR !%d: %s", mr_iid, exc)
            return False

        if mr.get("state") != "opened":
            logger.debug("MR !%d is not open (state=%s)", mr_iid, mr.get("state"))
            return False

        if mr.get("merge_status") not in ("can_be_merged", ""):
            merge_status = mr.get("merge_status", "")
            if merge_status and merge_status != "can_be_merged":
                logger.debug("MR !%d has merge conflicts: %s", mr_iid, merge_status)
                return False

        # Check pipeline
        try:
            pipeline = self.pipeline.get_latest_pipeline(project_id, mr_iid)
        except Exception:
            pipeline = {}

        if pipeline:
            if self.pipeline.is_pipeline_failed(pipeline):
                logger.debug("MR !%d pipeline failed", mr_iid)
                return False
            if self.pipeline.is_pipeline_running(pipeline):
                logger.debug("MR !%d pipeline still running", mr_iid)
                return False

        return True

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def complete_merge(
        self,
        project_id: Any,
        mr_iid: int,
        squash: bool = True,
    ) -> Dict[str, Any]:
        """Merge an approved MR, optionally squashing commits.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            mr_iid: MR internal ID (iid).
            squash: Whether to squash commits on merge (default: ``True``).

        Returns:
            Merged MR dict.

        Raises:
            GitLabClientError: On API error.
            RuntimeError: If the MR is not in a mergeable state.
        """
        if not self.can_merge(project_id, mr_iid):
            raise RuntimeError(
                f"MR !{mr_iid} in project {project_id} is not ready to merge"
            )
        logger.info("Merging MR !%d in project %s (squash=%s)", mr_iid, project_id, squash)
        merge_message = f"Merge MR !{mr_iid} (Agent-Engineers auto-merge)"
        return self.client.merge_mr(
            project_id, mr_iid, merge_commit_message=merge_message
        )
