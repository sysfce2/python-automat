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


@dataclass(frozen=True)
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
            self.builder._register(
                old=self,
                new=new_state,
                impl=decoratee,
                input=input_method,
                requires_data=False,
                produces_data=False,
            )
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
            self.builder._register(
                old=self,
                new=new_state,
                impl=decoratee,
                input=input_method,
                requires_data=False,
                produces_data=True,
            )
            return decoratee

        return decorator


@dataclass(frozen=True)
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
            # FIXME: actually register setup
            return decoratee

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
            # FIXME: actually register cleanup
            return decoratee

        return decorator

    def transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, P], R],
        new_state: TypifiedState[InputProtocol, Core],
    ) -> Decorator[Concatenate[InputProtocol, Core, Data, P], R]:
        def decorator(
            decoratee: Callable[Concatenate[InputProtocol, Core, Data, P], R]
        ) -> Callable[Concatenate[InputProtocol, Core, Data, P], R]:
            self.builder._register(
                old=self,
                new=new_state,
                impl=decoratee,
                input=input_method,
                requires_data=True,
                produces_data=False,
            )
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
            self.builder._register(
                old=self,
                new=new_state,
                impl=decoratee,
                input=input_method,
                requires_data=True,
                produces_data=True,
            )
            return decoratee

        return decorator


@dataclass
class TypifiedInput:
    name: str


@dataclass
class TypifiedBase(Generic[Core]):
    __automat_core__: Core
    __automat_transitioner__: Transitioner[
        TypifiedState | TypifiedDataState, str, Callable[..., object]
    ]
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
    method: Callable[..., object],
) -> Callable[..., object]:

    method_input = method.__name__

    def implementation(
        self: TypifiedBase[Core], /, *args: object, **kwargs: object
    ) -> object:
        transitioner = self.__automat_transitioner__
        [[impl_method], tracer] = transitioner.transition(method_input)
        result: Any = impl_method(self, *args, **kwargs)
        return result

    return implementation


def implify(
    method: Callable[..., Any], requires_data: bool, produces_data: bool
) -> Callable[..., object]:

    def theimpl(self: TypifiedBase[Core], /, *args: object, **kwargs: object) -> object:
        extra_args = [self, self.__automat_core__]
        if requires_data:
            extra_args += [self.__automat_data__]
        # if anything is invoked reentrantly here, then we can't possibly have
        # set __automat_data__ and the data argument to the reentrant method
        # will be wrong.  we *need* to split out the construction / state-enter
        # hook, because it needs to run separately. 
        result = method(*extra_args, *args, **kwargs)
        if produces_data:
            result, self.__automat_data__ = result
        return result

    return theimpl


@dataclass(eq=False)
class TypifiedBuilder(Generic[InputProtocol, Core]):
    protocol: ProtocolAtRuntime[InputProtocol]
    core_type: type[Core]

    _no_data_transitions: list[NoDataTransition] = field(default_factory=list)
    _data_transitions: list[DataTransition] = field(default_factory=list)
    automaton: Automaton[
        TypifiedState | TypifiedDataState, str, Callable[..., object]
    ] = field(default_factory=Automaton)
    _initial: bool = True

    def state(self, name: str) -> TypifiedState[InputProtocol, Core]:
        state = TypifiedState(name, self)
        if self._initial:
            self._initial = False
            self.automaton.initialState = state
        return state

    def data_state(
        self, name: str, data_type: type[Data]
    ) -> TypifiedDataState[InputProtocol, Core, Data]:
        assert not self._initial, "initial state cannot require state-specific data"
        return TypifiedDataState(name, self)

    def _register(
        self,
        *,
        old: (
            TypifiedDataState[InputProtocol, Core, Data]
            | TypifiedState[InputProtocol, Core]
        ),
        new: (
            TypifiedDataState[InputProtocol, Core, OtherData]
            | TypifiedState[InputProtocol, Core]
        ),
        impl: Callable[..., object],
        input: Callable[
            [
                InputProtocol,
            ],
            object,
        ],
        requires_data: bool,
        produces_data: bool,
    ) -> None:
        print(f"REGISTER {impl=}, {requires_data=}, {produces_data=}")
        self.automaton.addTransition(
            old,
            input.__name__,
            new,
            tuple(
                [
                    implify(
                        impl, requires_data=requires_data, produces_data=produces_data
                    )
                ]
            ),
        )

    def build(self) -> Callable[[Core], InputProtocol]:
        namespace = {
            method_name: implement_method(getattr(self.protocol, method_name))
            for method_name in actuallyDefinedProtocolMethods(self.protocol)
        }

        runtime_type: type[TypifiedBase[Core]] = type(
            f"Typified<{runtime_name(self.protocol)}>",
            tuple([TypifiedBase]),
            namespace,
        )

        def create(core: Core) -> InputProtocol:
            result: Any = runtime_type(
                core, Transitioner(self.automaton, self.automaton.initialState)
            )
            return result

        return create
