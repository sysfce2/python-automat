from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import wraps
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
FactoryParams = ParamSpec("FactoryParams")
OtherFactoryParams = ParamSpec("OtherFactoryParams")


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
            self.builder._register_plain(
                old=self,
                new=new_state,
                impl=decoratee,
                input=input_method,
                requires_data=False,
            )
            return decoratee

        return decorator

    def data_transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, FactoryParams], R],
        new_state: TypifiedDataState[
            InputProtocol, Core, OtherData, OtherFactoryParams
        ],
    ) -> Decorator[Concatenate[InputProtocol, Core, OtherFactoryParams], R]:
        def decorator(
            decoratee: Callable[Concatenate[InputProtocol, Core, OtherFactoryParams], R]
        ) -> Callable[Concatenate[InputProtocol, Core, OtherFactoryParams], R]:
            self.builder._register_data(
                old=self,
                new=new_state,
                impl=decoratee,
                input=input_method,
                requires_data=False,
            )
            return decoratee

        return decorator


@dataclass(frozen=True)
class TypifiedDataState(Generic[InputProtocol, Core, Data, FactoryParams]):
    name: str
    builder: TypifiedBuilder[InputProtocol, Core]
    factory: Callable[Concatenate[InputProtocol, Core, FactoryParams], Data]

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
            self.builder._register_plain(
                old=self,
                new=new_state,
                impl=decoratee,
                input=input_method,
                requires_data=True,
            )
            return decoratee

        return decorator

    def data_transition(
        self,
        input_method: Callable[Concatenate[InputProtocol, OtherFactoryParams], R],
        new_state: TypifiedDataState[
            InputProtocol, Core, OtherData, OtherFactoryParams
        ],
    ) -> Decorator[Concatenate[InputProtocol, Core, Data, OtherFactoryParams], R]:
        def decorator(
            decoratee: Callable[
                Concatenate[InputProtocol, Core, Data, OtherFactoryParams], R
            ]
        ) -> Callable[Concatenate[InputProtocol, Core, Data, OtherFactoryParams], R]:
            self.builder._register_data(
                old=self,
                new=new_state,
                impl=decoratee,
                input=input_method,
                requires_data=True,
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
    __automat_initializing_data__: bool = False


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
    """
    Construct a function for populating in the synthetic provider of the Input
    Protocol to a L{TypifiedBuilder}.  It should have a signature matching that
    of the C{method} parameter, a function from that protocol.
    """

    method_input = method.__name__

    def implementation(
        self: TypifiedBase[Core], /, *args: object, **kwargs: object
    ) -> object:
        transitioner = self.__automat_transitioner__
        [outputs, tracer] = transitioner.transition(method_input)
        print(f"{outputs=}")
        result: Any = None
        for output in outputs:
            # here's the idea: there will be a state-setup output and a
            # state-teardown output. state-setup outputs are added to the
            # *beginning* of any entry into a state, so that by the time you
            # are running the *implementation* of a method that has entered
            # that state, the protocol is in a self-consistent state and can
            # run reentrant outputs.  not clear that state-teardown outputs are
            # necessary
            print(f"invoking {output=}")
            result = output(self, result, *args, **kwargs)
        return result
    implementation.__qualname__ = implementation.__name__ = f"<implementation for {method}>"

    return implementation


def create_transition_output(
    method: Callable[..., Any], requires_data: bool
) -> Callable[..., object]:
    """
    This is the thing that goes into the automaton's outputs list, and thus
    (per the implementation of L{implement_method}) takes the 'self' of the
    TypifiedBase instance (i.e. the synthetic protocol implementation) and the
    previous result computed by the former output, which will be None
    initially.
    """

    def theimpl(
        self: TypifiedBase[Core],
        previous_result: object,
        /,
        *args: object,
        **kwargs: object,
    ) -> object:
        extra_args = [self, self.__automat_core__]
        if requires_data:
            if self.__automat_initializing_data__:
                raise RuntimeError(
                    "data factories cannot invoke their state machines reentrantly"
                )
            extra_args += [self.__automat_data__]
        # if anything is invoked reentrantly here, then we can't possibly have
        # set __automat_data__ and the data argument to the reentrant method
        # will be wrong.  we *need* to split out the construction / state-enter
        # hook, because it needs to run separately.
        return method(*extra_args, *args, **kwargs)

    theimpl.__qualname__ = theimpl.__name__ = f"<transition output for {method}>"

    return theimpl


def relay_data() -> Callable[..., object]:
    """
    relay the data over to the next output
    """

    def relayer(
        self: TypifiedBase[Core],
        previous_result: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        return self.__automat_data__

    return relayer


def implement_data_factory(data_factory: Callable[..., Data]) -> Callable[..., Data]:
    """
    Construct an output for the given data objects.
    """

    def dataimpl(
        self: TypifiedBase[Core],
        previous_result: object,
        *args: object,
        **kwargs: object,
    ) -> Data:
        print(f"DI: {data_factory=} {args=} {kwargs=}")
        new_data = data_factory(self, self.__automat_core__, *args, **kwargs)
        self.__automat_data__ = new_data
        return new_data
    dataimpl.__qualname__ = dataimpl.__name__ = f"<data factory for {data_factory}>"

    return dataimpl


@dataclass(eq=False)
class TypifiedBuilder(Generic[InputProtocol, Core]):
    protocol: ProtocolAtRuntime[InputProtocol]
    core_type: type[Core]
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
        self,
        name: str,
        data_factory: Callable[Concatenate[InputProtocol, Core, P], Data],
    ) -> TypifiedDataState[InputProtocol, Core, Data, P]:
        assert not self._initial, "initial state cannot require state-specific data"
        return TypifiedDataState(name, self, data_factory)

    def _register_plain(
        self,
        *,
        old: (
            TypifiedDataState[InputProtocol, Core, Data, P]
            | TypifiedState[InputProtocol, Core]
        ),
        new: TypifiedState[InputProtocol, Core],
        impl: Callable[..., object],
        input: Callable[
            [
                InputProtocol,
            ],
            object,
        ],
        requires_data: bool,
    ) -> None:
        print(f"REGISTER1 {impl=}, {requires_data=}")
        self.automaton.addTransition(
            old,
            input.__name__,
            new,
            tuple([create_transition_output(impl, requires_data=requires_data)]),
        )

    def _register_data(
        self,
        *,
        old: (
            TypifiedDataState[InputProtocol, Core, Data, P]
            | TypifiedState[InputProtocol, Core]
        ),
        new: TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams],
        impl: Callable[..., object],
        input: Callable[
            [
                InputProtocol,
            ],
            object,
        ],
        requires_data: bool,
    ):
        """
        registering a transition *to* a data state, which may require
        constructing a data object.
        """
        impls: list[Callable[..., object]] = []
        # Either way, we still need to run the actual implementation
        impls.append(create_transition_output(impl, requires_data=requires_data))
        if old is new:
            # If this transition is in the same state that we were in
            # previously, then __automat_data__ should still be the same, let's
            # just pass it along.
            impls.append(relay_data())
        else:
            # Otherwise, let's construct a new one.
            impls.append(implement_data_factory(new.factory))
        self.automaton.addTransition(
            old,
            input.__name__,
            new,
            tuple(impls),
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
