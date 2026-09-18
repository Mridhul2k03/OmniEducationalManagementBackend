"""
Context management for multi-tenancy and request tracing.
Uses contextvars to be safe for both synchronous and asynchronous execution.
"""
from contextvars import ContextVar
from typing import Optional, Any

_current_tenant: ContextVar[Optional[Any]] = ContextVar("current_tenant", default=None)
_current_request_id: ContextVar[Optional[str]] = ContextVar("current_request_id", default=None)


def set_current_tenant(tenant: Optional[Any]) -> None:
    _current_tenant.set(tenant)


def get_current_tenant() -> Optional[Any]:
    return _current_tenant.get()


def clear_current_tenant() -> None:
    _current_tenant.set(None)


def set_current_request_id(request_id: Optional[str]) -> None:
    _current_request_id.set(request_id)


def get_current_request_id() -> Optional[str]:
    return _current_request_id.get()
