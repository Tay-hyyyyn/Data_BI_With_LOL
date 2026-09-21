"""Shared error handling so routers stay free of repetitive try/except blocks."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

ErrorTypes = type[BaseException] | tuple[type[BaseException], ...]
Rule = tuple[ErrorTypes, int, str | None]


class DomainError(Exception):
    """Raised by services for conditions that map to a specific HTTP status."""

    status_code = 400

    def __init__(self, message: str = "", status_code: int | None = None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": str(error)})


def not_found(message: str) -> Rule:
    return (KeyError, 404, message)


def unprocessable(*types: type[BaseException]) -> Rule:
    return (types, 422, None)


@contextmanager
def api_errors(*rules: Rule) -> Iterator[None]:
    """Translate service exceptions into HTTP errors.

    Rules are checked in order; a `None` message uses `str(error)`. Unmatched exceptions propagate.
    """
    try:
        yield
    except HTTPException:
        raise
    except Exception as error:
        for types, status, message in rules:
            if isinstance(error, types):
                raise HTTPException(status, str(error) if message is None else message) from error
        raise
