from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Concatenate, Generic, ParamSpec, TypeVar

from ._core import Automaton, Transitioner
from ._runtimeproto import (
    ProtocolAtRuntime,
    actuallyDefinedProtocolMethods,
    runtime_name,
)

InputProtocol = TypeVar("InputProtocol")
InputProtoSelf = TypeVar("InputProtoSelf")
SharedCore = TypeVar("SharedCore")
StateSpecificData = TypeVar("StateSpecificData")
P = ParamSpec("P")
FactoryParams = ParamSpec("FactoryParams")
R = TypeVar("R")
OtherInputProtocol = TypeVar("OtherInputProtocol")
OtherStateSpecificData = TypeVar("OtherStateSpecificData")
OtherFactoryParams = ParamSpec("OtherFactoryParams")


@dataclass
class TypifiedState(Generic[InputProtocol, SharedCore]):
    name: str
    builder: TypifiedBuilder[InputProtocol, SharedCore]

    def transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, P], R],
        new_state: AnyState,
    ) -> Callable[
        [Callable[Concatenate[InputProtocol, SharedCore, P], R]],
        Callable[Concatenate[InputProtocol, SharedCore, P], R],
    ]:
        def decorator(
            decoratee: Callable[Concatenate[InputProtocol, SharedCore, P], R]
        ) -> Callable[Concatenate[InputProtocol, SharedCore, P], R]:
            # FIXME: actually register transition
            return decoratee

        return decorator


@dataclass
class TypifiedStatefulState(
    Generic[InputProtocol, SharedCore, StateSpecificData, FactoryParams]
):
    name: str
    builder: TypifiedBuilder[InputProtocol, SharedCore]
    factory: Callable[FactoryParams, StateSpecificData]

    def stateful_setup(
        self,
    ) -> Callable[
        [Callable[[InputProtocol, SharedCore, StateSpecificData], None]],
        Callable[[InputProtocol, SharedCore, StateSpecificData], None],
    ]:
        def decorator(
            decoratee: Callable[[InputProtocol, SharedCore, StateSpecificData], None]
        ) -> Callable[[InputProtocol, SharedCore, StateSpecificData], None]:
            return decoratee

        # FIXME: actually register setup
        return decorator

    def stateful_cleanup(
        self,
    ) -> Callable[
        [Callable[[InputProtocol, SharedCore, StateSpecificData], None]],
        Callable[[InputProtocol, SharedCore, StateSpecificData], None],
    ]:
        def decorator(
            decoratee: Callable[[InputProtocol, SharedCore, StateSpecificData], None]
        ) -> Callable[[InputProtocol, SharedCore, StateSpecificData], None]:
            return decoratee

        # FIXME: actually register cleanup
        return decorator

    def stateful_convey(
        self,
        input_method: Callable[Concatenate[InputProtocol, P], R],
        new_state: TypifiedStatefulState[
            OtherInputProtocol, SharedCore, OtherStateSpecificData, OtherFactoryParams
        ],
    ) -> Callable[
        [
            Callable[
                Concatenate[InputProtocol, SharedCore, StateSpecificData, P],
                tuple[R, OtherStateSpecificData],
            ]
        ],
        Callable[
            Concatenate[InputProtocol, SharedCore, StateSpecificData, P],
            tuple[R, OtherStateSpecificData],
        ],
    ]:
        def decorator(
            decoratee: Callable[
                Concatenate[InputProtocol, SharedCore, StateSpecificData, P],
                tuple[R, OtherStateSpecificData],
            ]
        ) -> Callable[
            Concatenate[InputProtocol, SharedCore, StateSpecificData, P],
            tuple[R, OtherStateSpecificData],
        ]:
            return decoratee

        return decorator

    def stateful_transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, P], R],
        new_state: AnyState,
    ) -> Callable[
        [Callable[Concatenate[InputProtocol, SharedCore, StateSpecificData, P], R]],
        Callable[Concatenate[InputProtocol, SharedCore, StateSpecificData, P], R],
    ]:
        def decorator(
            decoratee: Callable[
                Concatenate[InputProtocol, SharedCore, StateSpecificData, P], R
            ]
        ) -> Callable[Concatenate[InputProtocol, SharedCore, StateSpecificData, P], R]:
            # FIXME: actually register transition
            return decoratee

        return decorator


AnyState = (
    TypifiedState[InputProtocol, SharedCore]
    | TypifiedStatefulState[InputProtocol, SharedCore, Any, ...]
)


@dataclass
class _TypicalBase(Generic[SharedCore]):
    _core: SharedCore
    _transitioner: Transitioner
    _state_specific_data: object | None = None

@dataclass
class NoDataTransition:
    input_name: str
    from_state: AnyState
    to_state: AnyState

@dataclass
class DataTransition(Generic[StateSpecificData]):
    input_name: str
    from_state: AnyState
    to_state: TypifiedStatefulState
    factory: Callable[[]]

@dataclass
class TypifiedBuilder(Generic[InputProtocol, SharedCore]):
    protocol: ProtocolAtRuntime[InputProtocol]
    core_type: type[SharedCore]

    _no_data_transitions: list[NoDataTransition] = field(default_factory=list)
    _data_transitions: list[DataTransition] = field(default_factory=list)

    def state(self, name: str) -> TypifiedState[InputProtocol, SharedCore]:
        return TypifiedState(name, self)

    def stateful_state(
        self,
        name: str,
        data_type: type[StateSpecificData],
        factory: Callable[P, StateSpecificData],
    ) -> TypifiedStatefulState[InputProtocol, SharedCore, StateSpecificData, P]:
        return TypifiedStatefulState(name, self, factory)

    def build(self) -> Callable[[SharedCore], InputProtocol]:
        namespace: dict[str, str] = {}
        runtime_type = type(
            f"Typified<{runtime_name(self.protocol)}>",
            tuple([_TypicalBase]),
            namespace,
        )
        return runtime_type
