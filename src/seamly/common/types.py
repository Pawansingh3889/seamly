"""Shared types and errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


class SeamlyError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Result[T]:
    """Every handler returns a Result; err carries a code and actionable message."""

    value: T | None = None
    error: SeamlyError | None = None
    events: list[Any] = field(default_factory=list)

    @classmethod
    def ok(cls, value: T | None = None) -> Result[T]:
        return cls(value=value)

    @classmethod
    def err(cls, code: str, message: str) -> Result[T]:
        return cls(error=SeamlyError(code, message))

    @property
    def is_err(self) -> bool:
        return self.error is not None

    def error_or_raise(self) -> SeamlyError:
        if self.error is None:
            raise AssertionError("expected an error but none was present")
        return self.error

    def value_or_raise(self) -> T:
        if self.error is not None:
            raise SeamlyError(self.error.code, self.error.message)
        if self.value is None:
            raise AssertionError("expected a value but none was present")
        return self.value
