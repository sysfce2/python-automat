from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar, overload

if sys.version_info < (3, 10):
    from typing_extensions import Concatenate, ParamSpec
else:
    from typing import Concatenate, ParamSpec

from ._core import Automaton, Transitioner
from ._runtimeproto import (
    ProtocolAtRuntime,
    actuallyDefinedProtocolMethods,
    runtime_name,
)

InputProtocol = TypeVar("InputProtocol")
InputProtoSelf = TypeVar("InputProtoSelf")
Core = TypeVar("Core")
Data = TypeVar("Data")
P = ParamSpec("P")
R = TypeVar("R")
OtherInputProtocol = TypeVar("OtherInputProtocol")
OtherData = TypeVar("OtherData")
Decorator = Callable[[Callable[P, R]], Callable[P, R]]


@dataclass
class TypifiedState(Generic[InputProtocol, Core]):
    name: str
    builder: TypifiedBuilder[InputProtocol, Core]

    def transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, P], R],
        new_state: TypifiedState[InputProtocol, Core],
    ) -> Decorator[Concatenate[InputProtocol, Core, P], R]:
        def decorator(
            decoratee: Callable[Concatenate[InputProtocol, Core, P], R]
        ) -> Callable[Concatenate[InputProtocol, Core, P], R]:
            # FIXME: actually register transition
            return decoratee

        return decorator

    def data_transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, P], R],
        new_state: TypifiedDataState[InputProtocol, Core, OtherData],
    ) -> Decorator[Concatenate[InputProtocol, Core, P], tuple[R, OtherData]]:
        def decorator(
            decoratee: Callable[
                Concatenate[InputProtocol, Core, P], tuple[R, OtherData]
            ]
        ) -> Callable[Concatenate[InputProtocol, Core, P], tuple[R, OtherData]]:
            # FIXME: actually register transition
            return decoratee

        return decorator


@dataclass
class TypifiedDataState(Generic[InputProtocol, Core, Data]):
    name: str
    builder: TypifiedBuilder[InputProtocol, Core]

    def data_setup(
        self,
    ) -> Callable[
        [Callable[[InputProtocol, Core, Data], None]],
        Callable[[InputProtocol, Core, Data], None],
    ]:
        def decorator(
            decoratee: Callable[[InputProtocol, Core, Data], None]
        ) -> Callable[[InputProtocol, Core, Data], None]:
            return decoratee

        # FIXME: actually register setup
        return decorator

    def data_cleanup(
        self,
    ) -> Callable[
        [Callable[[InputProtocol, Core, Data], None]],
        Callable[[InputProtocol, Core, Data], None],
    ]:
        def decorator(
            decoratee: Callable[[InputProtocol, Core, Data], None]
        ) -> Callable[[InputProtocol, Core, Data], None]:
            return decoratee

        # FIXME: actually register cleanup
        return decorator

    def transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, P], R],
        new_state: TypifiedState[InputProtocol, Core],
    ) -> Decorator[Concatenate[InputProtocol, Core, Data, P], R]:
        def decorator(
            decoratee: Callable[Concatenate[InputProtocol, Core, Data, P], R]
        ) -> Callable[Concatenate[InputProtocol, Core, Data, P], R]:
            # FIXME: actually register transition
            return decoratee

        return decorator

    def data_transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, P], R],
        new_state: TypifiedDataState[InputProtocol, Core, OtherData],
    ) -> Decorator[Concatenate[InputProtocol, Core, Data, P], tuple[R, OtherData]]:
        def decorator(
            decoratee: Callable[
                Concatenate[InputProtocol, Core, Data, P], tuple[R, OtherData]
            ]
        ) -> Callable[Concatenate[InputProtocol, Core, Data, P], tuple[R, OtherData]]:
            # FIXME: actually register transition
            return decoratee

        return decorator


@dataclass
class _TypicalBase(Generic[Core]):
    __automat_core__: Core
    __automat_transitioner__: Transitioner
    __automat_methods__: dict[str, dict[str, Callable[..., Any]]]
    __automat_data__: object | None = None


@dataclass
class NoDataTransition:
    input_name: str
    implementation: Callable[..., object]


@dataclass
class DataTransition(Generic[Data]):
    """
    A transition I{to} a state that constructs.
    """

    input_name: str
    implementation: Callable[..., tuple[object, Data]]


def implement_method(
    method: Callable[..., object], requires_data: bool, produces_data: bool
) -> Callable[..., object]:
    method_name = method.__name__

    def implementation(
        self: _TypicalBase, /, *args: object, **kwargs: object
    ) -> object:
        transitioner = self.__automat_transitioner__
        [[impl_method], tracer] = transitioner.transition(method_name)
        if requires_data:
            args = (self.__automat_data__, *args)
        result: Any = impl_method(self, self.__automat_core__, *args, **kwargs)
        if produces_data:
            result, self.__automat_data__ = result
        return result

    return implementation


@dataclass
class TypifiedBuilder(Generic[InputProtocol, Core]):
    protocol: ProtocolAtRuntime[InputProtocol]
    core_type: type[Core]

    _no_data_transitions: list[NoDataTransition] = field(default_factory=list)
    _data_transitions: list[DataTransition] = field(default_factory=list)

    def state(self, name: str) -> TypifiedState[InputProtocol, Core]:
        return TypifiedState(name, self)

    def data_state(
        self, name: str, data_type: type[Data]
    ) -> TypifiedDataState[InputProtocol, Core, Data]:
        return TypifiedDataState(name, self)

    def build(self) -> Callable[[Core], InputProtocol]:
        namespace: dict[str, str] = {}
        runtime_type = type(
            f"Typified<{runtime_name(self.protocol)}>",
            tuple([_TypicalBase]),
            namespace,
        )
        return runtime_type
