"""
Workaround for U{the lack of TypeForm
<https://github.com/python/mypy/issues/9773>}.
"""

from __future__ import annotations

import sys

from typing import TYPE_CHECKING, Callable, Protocol, TypeVar

from inspect import signature, Signature

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


def _liveSignature(method: Callable[..., object]) -> Signature:
    """
    Get a signature with evaluated annotations.
    """
    # TODO: could this be replaced with get_type_hints?
    result = signature(method)
    for param in result.parameters.values():
        annotation = param.annotation
        if isinstance(annotation, str):
            scope = getattr(method, "__globals__", None)
            if scope is None:
                module = sys.modules[method.__module__]
                scope = module.__dict__
            param._annotation = eval(annotation, scope)  # type:ignore
    return result


