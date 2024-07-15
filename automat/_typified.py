from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Concatenate, Generic, ParamSpec, TypeVar

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
class TypifiedBuilder(Generic[InputProtocol, SharedCore]):
    core_type: type[SharedCore]

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
        # FIXME: obviously
        return None             # type:ignore[return-value]
