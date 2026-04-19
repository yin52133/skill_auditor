from __future__ import annotations


class SkillAuditorError(Exception):
    """Structured command error with a stable error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
