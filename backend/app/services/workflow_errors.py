"""Workflow exceptions shared by the engine, guards and side effects."""

from __future__ import annotations

from typing import Any


class WorkflowError(Exception):
    """An expected workflow failure with an HTTP representation."""

    status_code = 409

    def __init__(self, message: str, *, detail: Any | None = None) -> None:
        super().__init__(message)
        self.detail = detail if detail is not None else message


class InvalidWorkflowTransition(WorkflowError):
    """Raised when an action is not legal for the current status or guards fail."""


class WorkflowPermissionError(WorkflowError):
    """Raised when the current role may not perform an action."""

    status_code = 403


class WorkflowValidationError(WorkflowError):
    """Raised when an action payload is incomplete or inconsistent."""

    status_code = 422


class WorkflowConfigurationError(WorkflowError):
    """Raised when required database configuration is missing."""

    status_code = 503


class WorkflowNotFoundError(WorkflowError):
    """Raised when an action references a record outside the application."""

    status_code = 404
