"""
Prompt Loading Utilities
========================

Functions for loading prompt templates from the prompts directory.
"""

import shutil
from pathlib import Path

PROMPTS_DIR: Path = Path(__file__).parent / "prompts"
SPECS_DIR: Path = Path(__file__).parent / "specs"


def load_prompt(name: str) -> str:
    """
    Load a prompt template from the prompts directory.

    Args:
        name: Prompt name (without .md extension)

    Returns:
        Prompt text content

    Raises:
        FileNotFoundError: If prompt file doesn't exist
        IOError: If prompt file cannot be read
    """
    # Reject names with path traversal sequences or absolute paths
    if ".." in name or name.startswith("/") or name.startswith("\\"):
        raise ValueError(f"Invalid prompt name: {name!r} (path traversal not allowed)")

    prompt_path: Path = PROMPTS_DIR / f"{name}.md"

    # Verify the resolved path is still within PROMPTS_DIR
    if not prompt_path.resolve().is_relative_to(PROMPTS_DIR.resolve()):
        raise ValueError(f"Invalid prompt name: {name!r} (resolves outside prompts directory)")

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}\n"
            f"Expected prompts directory: {PROMPTS_DIR}\n"
            f"This may indicate an incomplete installation."
        )

    try:
        return prompt_path.read_text()
    except OSError as e:
        raise OSError(
            f"Failed to read prompt file {prompt_path}: {e}\nCheck file permissions."
        ) from e


def get_initializer_task(project_dir: Path) -> str:
    """
    Get the task message for initializing a new project.

    This is sent to the orchestrator, which will delegate to specialized agents.

    Args:
        project_dir: Directory for the project

    Returns:
        Task message with project_dir substituted
    """
    template = load_prompt("initializer_task")
    return template.format(project_dir=project_dir)


def get_continuation_task(project_dir: Path) -> str:
    """
    Get the task message for continuing work on an existing project.

    This is sent to the orchestrator, which will delegate to specialized agents.

    Args:
        project_dir: Directory for the project

    Returns:
        Task message with project_dir substituted
    """
    template = load_prompt("continuation_task")
    return template.format(project_dir=project_dir)


def find_active_spec() -> Path:
    """
    Find the active spec file in the specs/ directory.

    Looks for spec files at the top level of specs/ (ignores specs/complete/).
    Returns the first .md or .txt file found.

    Returns:
        Path to the active spec file

    Raises:
        FileNotFoundError: If no spec file is found
    """
    # Look for .md files first, then .txt
    for pattern in ("*.md", "*.txt"):
        specs = sorted(SPECS_DIR.glob(pattern))
        if specs:
            return specs[0]

    raise FileNotFoundError(
        f"No spec file found in {SPECS_DIR}\n"
        f"Add a .md or .txt spec file to the specs/ directory."
    )


def copy_spec_to_project(project_dir: Path, spec_path: Path | None = None) -> None:
    """
    Copy a spec file into the project directory for the agent to read.

    Args:
        project_dir: Target project directory
        spec_path: Explicit path to spec file. If None, auto-detects from specs/.

    Raises:
        FileNotFoundError: If source spec file doesn't exist
        IOError: If copy operation fails
    """
    spec_source: Path = spec_path if spec_path is not None else find_active_spec()
    spec_dest: Path = project_dir / "app_spec.txt"

    if not spec_source.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_source}")

    if not spec_dest.exists():
        try:
            shutil.copy(spec_source, spec_dest)
            print(f"Copied {spec_source.name} to {project_dir}")
        except OSError as e:
            raise OSError(
                f"Failed to copy spec to {spec_dest}: {e}\nCheck disk space and permissions."
            ) from e
