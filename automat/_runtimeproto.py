"""
Workaround for U{the lack of TypeForm
<https://github.com/python/mypy/issues/9773>}.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Protocol, TypeVar

T = TypeVar("T")

ProtocolAtRuntime = Callable[[], T]


def runtime_name(x: ProtocolAtRuntime[T]) -> str:
    return x.__name__  # type:ignore[attr-defined]


from inspect import getmembers, isfunction

emptyProtocolMethods: frozenset[str]
if not TYPE_CHECKING:
    emptyProtocolMethods = frozenset(
        name
        for name, each in getmembers(type("Example", tuple([Protocol]), {}), isfunction)
    )


def actuallyDefinedProtocolMethods(protocol: object) -> frozenset[str]:
    """
    Attempt to ignore implementation details, and get all the methods that the
    protocol actually defines.

    that includes locally defined methods and also those defined in inherited
    superclasses.
    """
    return (
        frozenset(name for name, each in getmembers(protocol, isfunction))
        - emptyProtocolMethods
    )
