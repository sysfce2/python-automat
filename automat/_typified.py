from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Iterable, TypeVar, overload

if sys.version_info < (3, 10):
    from typing_extensions import Concatenate, ParamSpec
else:
    from typing import Concatenate, ParamSpec

from ._core import Automaton, Transitioner
from ._runtimeproto import (
    ProtocolAtRuntime,
    _liveSignature,
    actuallyDefinedProtocolMethods,
    runtime_name,
)

InputProtocol = TypeVar("InputProtocol")
Core = TypeVar("Core")
Data = TypeVar("Data")
P = ParamSpec("P")
R = TypeVar("R")
OtherInputProtocol = TypeVar("OtherInputProtocol")
OtherData = TypeVar("OtherData")
AnyArgs = ParamSpec("AnyArgs")
AnyResult = TypeVar("AnyResult")
Decorator = Callable[[Callable[P, R]], Callable[P, R]]
FactoryParams = ParamSpec("FactoryParams")
OtherFactoryParams = ParamSpec("OtherFactoryParams")
AnyCallable = TypeVar("AnyCallable", bound=Callable[..., Any])


@dataclass(frozen=True)
class TypifiedState(Generic[InputProtocol, Core]):
    name: str
    builder: TypifiedBuilder[InputProtocol, Core]

    def edge(
        self,
        method: Callable[Concatenate[InputProtocol, P], None],
        target: (
            TypifiedState[InputProtocol, Core]
            | TypifiedDataState[InputProtocol, Core, OtherData, P]
        ),
    ) -> None:
        @self.transition(method, target)
        def null(*args: object, **kwargs: object) -> None: ...

    def loop(self, method: Callable[Concatenate[InputProtocol, P], None]) -> None:
        self.edge(method, self)

    @overload
    def transition(
        self,
        method: Callable[Concatenate[InputProtocol, P], R],
        target: TypifiedState[InputProtocol, Core],
    ) -> Decorator[Concatenate[InputProtocol, Core, P], R]: ...
    @overload
    def transition(
        self,
        method: Callable[Concatenate[InputProtocol, OtherFactoryParams], R],
        target: TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams],
    ) -> Decorator[Concatenate[InputProtocol, Core, OtherFactoryParams], R]: ...
    @overload
    def transition(
        self,
        method: Callable[Concatenate[InputProtocol, P], R],
    ) -> Decorator[Concatenate[InputProtocol, Core, P], R]: ...
    def transition(
        self,
        method: Callable[..., object],
        target: (
            TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
            | TypifiedState[InputProtocol, Core]
            | None
        ) = None,
    ) -> Decorator[AnyArgs, AnyResult]:
        reg = self.builder._register_transition

        def decorator(
            decoratee: Callable[AnyArgs, AnyResult]
        ) -> Callable[AnyArgs, AnyResult]:
            # Type puzzle: I could not figure out a declared type for the
            # 'new=' parameter here that would let me do this invocation just
            # once.
            if target is not None:
                reg(old=self, new=target, impl=decoratee, input=method)
            else:
                reg(old=self, new=self, impl=decoratee, input=method)
            return decoratee

        return decorator

    def _produce_outputs(
        self,
        impl: Callable[..., object],
        old: (
            TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
            | TypifiedState[InputProtocol, Core]
        ),
    ) -> Iterable[Callable[..., object]]:
        yield create_method_output(impl, isinstance(old, TypifiedDataState))


@dataclass(frozen=True)
class TypifiedDataState(Generic[InputProtocol, Core, Data, FactoryParams]):
    name: str
    builder: TypifiedBuilder[InputProtocol, Core]
    factory: Callable[Concatenate[InputProtocol, Core, FactoryParams], Data]

    def data_setup(self) -> Decorator[[InputProtocol, Core, Data], None]:
        def decorator(
            decoratee: Callable[[InputProtocol, Core, Data], None]
        ) -> Callable[[InputProtocol, Core, Data], None]:
            # FIXME: actually register setup
            return decoratee

        return decorator

    def data_cleanup(self) -> Decorator[[InputProtocol, Core, Data], None]:
        def decorator(
            decoratee: Callable[[InputProtocol, Core, Data], None]
        ) -> Callable[[InputProtocol, Core, Data], None]:
            # FIXME: actually register cleanup
            return decoratee

        return decorator

    def edge(
        self,
        method: Callable[Concatenate[InputProtocol, P], None],
        target: (
            TypifiedState[InputProtocol, Core]
            | TypifiedDataState[InputProtocol, Core, OtherData, P]
        ),
    ) -> None:
        @self.transition(method, target)
        def null(*args: object, **kwargs: object) -> None: ...

    def loop(self, method: Callable[Concatenate[InputProtocol, P], None]) -> None:
        # inference problem???
        self.edge(method, self)  # type:ignore[misc]

    @overload
    def transition(
        self,
        method: Callable[Concatenate[InputProtocol, P], R],
        target: TypifiedState[InputProtocol, Core],
    ) -> Decorator[Concatenate[InputProtocol, Core, Data, P], R]: ...
    @overload
    def transition(
        self, method: Callable[Concatenate[InputProtocol, P], R]
    ) -> Decorator[Concatenate[InputProtocol, Core, Data, P], R]: ...
    @overload
    def transition(
        self,
        method: Callable[Concatenate[InputProtocol, OtherFactoryParams], R],
        target: TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams],
    ) -> Decorator[Concatenate[InputProtocol, Core, Data, OtherFactoryParams], R]: ...
    def transition(
        self,
        method: Callable[..., object],
        target: (
            TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
            | TypifiedState[InputProtocol, Core]
            | None
        ) = None,
    ) -> Decorator[AnyArgs, AnyResult]:
        reg = self.builder._register_transition

        def decorator(
            decoratee: Callable[AnyArgs, AnyResult]
        ) -> Callable[AnyArgs, AnyResult]:
            # Type puzzle: I could not figure out a declared type for the
            # 'new=' parameter here that would let me do this invocation just
            # once.
            if target is not None:
                reg(old=self, new=target, impl=decoratee, input=method)
            else:
                reg(old=self, new=self, impl=decoratee, input=method)
            return decoratee

        return decorator

    def _produce_outputs(
        self,
        impl: Callable[..., object],
        old: (
            TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
            | TypifiedState[InputProtocol, Core]
        ),
    ) -> Iterable[Callable[..., object]]:
        if self is not old:
            yield create_data_output(self.factory)
        yield create_method_output(impl, isinstance(old, TypifiedDataState))


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
    __automat_postponed__: list[Callable[[], None]] | None = None


def implement_method(
    method: Callable[..., object],
) -> Callable[..., object]:
    """
    Construct a function for populating in the synthetic provider of the Input
    Protocol to a L{TypifiedBuilder}.  It should have a signature matching that
    of the C{method} parameter, a function from that protocol.
    """

    method_input = method.__name__

    # side-effects can be re-ordered until later.  If you need to compute a
    # value in your method, then obviously it can't be invoked reentrantly.
    return_annotation = _liveSignature(method).return_annotation
    is_procedure = return_annotation is None

    def implementation(
        self: TypifiedBase[Core], /, *args: object, **kwargs: object
    ) -> object:
        transitioner = self.__automat_transitioner__
        data_at_start = self.__automat_data__
        if self.__automat_postponed__ is not None:
            if not is_procedure:
                raise RuntimeError(
                    f"attempting to reentrantly run {method.__qualname__} "
                    f"but it wants to return {return_annotation!r} not None "
                    f"({return_annotation is None} {is_procedure})"
                )

            def rerunme() -> None:
                implementation(self, *args, **kwargs)

            self.__automat_postponed__.append(rerunme)
            return None
        postponed = self.__automat_postponed__ = []
        try:
            try:
                [outputs, tracer] = transitioner.transition(method_input)
            except:
                import traceback

                traceback.print_exc()
                raise
            result: Any = None
            for output in outputs:
                # here's the idea: there will be a state-setup output and a
                # state-teardown output. state-setup outputs are added to the
                # *beginning* of any entry into a state, so that by the time you
                # are running the *implementation* of a method that has entered
                # that state, the protocol is in a self-consistent state and can
                # run reentrant outputs.  not clear that state-teardown outputs are
                # necessary
                result = output(self, data_at_start, *args, **kwargs)
        finally:
            self.__automat_postponed__ = None
        while postponed:
            postponed.pop(0)()
        return result

    implementation.__qualname__ = implementation.__name__ = (
        f"<implementation for {method}>"
    )

    return implementation


def create_method_output(
    method: Callable[..., Any], requires_data: bool
) -> Callable[..., object]:
    """
    This is the thing that goes into the automaton's outputs list, and thus
    (per the implementation of L{implement_method}) takes the 'self' of the
    TypifiedBase instance (i.e. the synthetic protocol implementation) and the
    previous result computed by the former output, which will be None
    initially.
    """

    sig = _liveSignature(method)
    # if requires_data:
    #     # 0: self, 1: self.__automat_core__, 2: self.__automat_data__
    #     param = list(sig.parameters.values())[2]
    #     ann = param.annotation

    def theimpl(
        self: TypifiedBase[Core],
        /,
        data_at_start: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        extra_args = [self, self.__automat_core__]
        if requires_data:
            # if self.__automat_initializing_data__:
            #     raise RuntimeError(
            #         f"data factories cannot invoke their state machines reentrantly {}"
            #     )
            # assert isinstance(
            #     data_at_start, ann
            # ), f"expected {param=} to be {ann=} but got {type(data_at_start)=} instead"
            extra_args += [data_at_start]
        # if anything is invoked reentrantly here, then we can't possibly have
        # set __automat_data__ and the data argument to the reentrant method
        # will be wrong.  we *need* to split out the construction / state-enter
        # hook, because it needs to run separately.
        return method(*extra_args, *args, **kwargs)

    theimpl.__qualname__ = theimpl.__name__ = f"<transition output for {method}>"

    return theimpl


def create_data_output(data_factory: Callable[..., Data]) -> Callable[..., Data]:
    """
    Construct an output for the given data objects.
    """

    def dataimpl(
        self: TypifiedBase[Core],
        data_at_start: object,
        *args: object,
        **kwargs: object,
    ) -> Data:
        assert (
            not self.__automat_initializing_data__
        ), "can't initialize while initializing"
        self.__automat_initializing_data__ = True
        try:
            new_data = data_factory(self, self.__automat_core__, *args, **kwargs)
            self.__automat_data__ = new_data
            return new_data
        finally:
            self.__automat_initializing_data__ = False

    dataimpl.__qualname__ = dataimpl.__name__ = f"<data factory for {data_factory}>"

    return dataimpl


@dataclass(eq=False)
class TypifiedBuilder(Generic[InputProtocol, Core]):
    protocol: ProtocolAtRuntime[InputProtocol]
    core_type: type[Core]
    automaton: Automaton[
        TypifiedState[InputProtocol, Core]
        | TypifiedDataState[InputProtocol, Core, Any, ...],
        str,
        Callable[..., object],
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

    def _register_transition(
        self,
        *,
        old: (
            TypifiedDataState[InputProtocol, Core, Data, P]
            | TypifiedState[InputProtocol, Core]
        ),
        new: (
            TypifiedState[InputProtocol, Core]
            | TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
        ),
        impl: Callable[..., object],
        input: Callable[[InputProtocol], object],
    ) -> None:
        self.automaton.addTransition(
            old,
            input.__name__,
            new,
            tuple(new._produce_outputs(impl, old)),
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
