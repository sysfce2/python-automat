# -*- test-case-name: automat._test.test_type_based -*-
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Iterable, TypeVar, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from graphviz import Digraph

if sys.version_info < (3, 10):
    from typing_extensions import Concatenate, ParamSpec, TypeAlias
else:
    from typing import Concatenate, ParamSpec, TypeAlias

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
P1 = ParamSpec("P1")
R = TypeVar("R")
OtherInputProtocol = TypeVar("OtherInputProtocol")
OtherData = TypeVar("OtherData")
AnyArgs = ParamSpec("AnyArgs")
AnyResult = TypeVar("AnyResult")
Decorator = Callable[[Callable[P, R]], Callable[P, R]]
FactoryParams = ParamSpec("FactoryParams")
OtherFactoryParams = ParamSpec("OtherFactoryParams")
AnyCallable = TypeVar("AnyCallable", bound=Callable[..., Any])
DataArgs = ParamSpec("DataArgs")


def pep614(t: R) -> R:
    """
    This is a workaround for Python 3.8, which has U{some restrictions on its
    grammar for decorators <https://peps.python.org/pep-0614/>}, and makes
    C{@state.to(other).upon(Protocol.input)} invalid syntax; for code that
    needs to run on these older Python versions, you can do
    C{@pep614(state.to(other).upon(Protocol.input))} instead.
    """
    return t


@dataclass()
class TransitionRegistrar(Generic[P, P1, R]):
    """
    This is a record of a transition that need finalizing.
    """

    _signature: Callable[P1, R]
    _old: AnyState
    _new: AnyState
    _nodata: bool = False
    _result: R | None = None
    _callback: Callable[P, R] | None = None

    def __post_init__(self) -> None:
        self._old.builder._registrars.append(self)

    def __call__(self, /, impl: Callable[P, R]) -> Callable[P, R]:
        """
        Finalize it with C{__call__} to indicate that there is an
        implementation to the transition, which can be treated as an output.
        """
        self._callback = impl
        builder = self._old.builder
        assert builder is self._new.builder, "states must be from the same builder"
        builder._automaton.addTransition(
            self._old,
            self._signature.__name__,
            self._new,
            tuple(self._new._produce_outputs(impl, self._old, self._nodata)),
        )
        return impl

    def returns(self, result: R) -> None:
        """
        Finalize it with C{.returns(constant)} to indicate that there is no
        method body, and the given result can just be yielded each time after
        the state transition.  The only output generated in this case would be
        the data-construction factory for the target state.
        """
        self._result = result
        self(lambda *args, **kwargs: result)

    def _checkComplete(self) -> None:
        """
        Raise an exception if the user forgot to decorate a method
        implementation or supply a return value for this transition.
        """
        # TODO: point at the line where `.to`/`.loop`/`.upon` are called so the
        # user can more immediately see the incomplete transition
        if not self._callback:
            raise ValueError(
                f"incomplete transition from {self._old.name} to "
                f"{self._new.name} upon {self._signature.__qualname__}: "
                "remember to use the transition as a decorator or call "
                "`.returns` on it."
            )


@dataclass(frozen=True)
class NoToNo(Generic[InputProtocol, Core]):
    """
    A transition registrar factory whose input method requires neither a data
    parameter nor a factory-signature match.
    """

    old: TypifiedState[InputProtocol, Core]
    new: TypifiedState[InputProtocol, Core]

    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R]
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, P], Concatenate[InputProtocol, P], R
    ]:
        return TransitionRegistrar(input, self.old, self.new)


@dataclass(frozen=True)
class NoToData(Generic[InputProtocol, Core, FactoryParams]):
    """
    A transition registrar factory whose input method does not take a data
    parameter but does require a factory-signature match.
    """

    old: TypifiedState[InputProtocol, Core]
    new: TypifiedDataState[InputProtocol, Core, object, FactoryParams]

    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R]
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, P], Concatenate[InputProtocol, P], R
    ]:
        return TransitionRegistrar(input, self.old, self.new)


@dataclass(frozen=True)
class DataToNo(Generic[InputProtocol, Core, Data]):
    """
    A transition registrar factory whose input method does take a data
    parameter but does not require a factory-signature match.
    """

    old: TypifiedDataState[InputProtocol, Core, Data, Any]
    new: TypifiedState[InputProtocol, Core]

    def upon(
        self, input: Callable[Concatenate[InputProtocol, FactoryParams], R]
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, Data, FactoryParams],
        Concatenate[InputProtocol, FactoryParams],
        R,
    ]:
        return TransitionRegistrar(input, self.old, self.new)


@dataclass(frozen=True)
class DataToData(Generic[InputProtocol, Core, Data, FactoryParams, OtherData]):
    """
    A transition registrar factory whose input method both takes a data
    parameter and requires a factory-signature match.
    """

    old: TypifiedDataState[InputProtocol, Core, Data, Any]
    new: TypifiedDataState[InputProtocol, Core, OtherData, FactoryParams]

    def upon(
        self, input: Callable[Concatenate[InputProtocol, FactoryParams], R]
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, Data, FactoryParams],
        Concatenate[InputProtocol, FactoryParams],
        R,
    ]:
        return TransitionRegistrar(input, self.old, self.new)

    def dataless(
        self,
    ) -> DataToDataNoData[InputProtocol, Core, Data, FactoryParams, OtherData]:
        return DataToDataNoData(self.old, self.new)


@dataclass(frozen=True)
class DataToSelf(Generic[InputProtocol, Core, Data]):
    """
    A transition registrar factory whose input method takes a data parameter,
    but who does not require a factory-signature match specifically because it
    is transitioning back to itself.
    """

    state: TypifiedDataState[InputProtocol, Core, Data, Any]

    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R]
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, Data, P], Concatenate[InputProtocol, P], R
    ]:
        return TransitionRegistrar(input, self.state, self.state)

    def dataless(self) -> DataToSelfNoData[InputProtocol, Core, Data]:
        return DataToSelfNoData(self.state)


# FIXME: better names for the next two classes
@dataclass(frozen=True)
class DataToDataNoData(Generic[InputProtocol, Core, Data, FactoryParams, OtherData]):
    old: TypifiedDataState[InputProtocol, Core, Data, Any]
    new: TypifiedDataState[InputProtocol, Core, OtherData, FactoryParams]

    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R]
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, P], Concatenate[InputProtocol, P], R
    ]:
        return TransitionRegistrar(input, self.old, self.new, True)


@dataclass(frozen=True)
class DataToSelfNoData(Generic[InputProtocol, Core, Data]):
    state: TypifiedDataState[InputProtocol, Core, Data, Any]

    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R]
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, P], Concatenate[InputProtocol, P], R
    ]:
        return TransitionRegistrar(input, self.state, self.state, True)


@dataclass(frozen=True)
class TypifiedState(Generic[InputProtocol, Core]):
    name: str
    builder: TypeMachineBuilder[InputProtocol, Core]

    def loop(self) -> NoToNo[InputProtocol, Core]:
        """
        An alias for C{self.to(self)}, for symmetry with
        L{TypifiedDataState.loop}.
        """
        return self.to(self)

    @overload
    def to(
        self, state: TypifiedState[InputProtocol, Core]
    ) -> NoToNo[InputProtocol, Core]: ...
    @overload
    def to(
        self,
        state: TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams],
    ) -> NoToData[InputProtocol, Core, OtherFactoryParams]: ...
    def to(
        self,
        state: (
            TypifiedState[InputProtocol, Core]
            | TypifiedDataState[InputProtocol, Core, Any, OtherFactoryParams]
        ),
    ) -> (
        NoToNo[InputProtocol, Core]
        | NoToData[
            InputProtocol,
            Core,
            OtherFactoryParams,
        ]
    ):
        """
        Declare a state transition to a new state.
        """
        if isinstance(state, TypifiedState):
            return NoToNo(self, state)
        else:
            return NoToData(self, state)

    def _produce_outputs(
        self,
        impl: Callable[..., object],
        old: (
            TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
            | TypifiedState[InputProtocol, Core]
        ),
        nodata: bool = False,
    ) -> Iterable[Callable[..., object]]:
        yield create_method_output(impl, isinstance(old, TypifiedDataState))


@dataclass(frozen=True)
class TypifiedDataState(Generic[InputProtocol, Core, Data, FactoryParams]):
    name: str
    builder: TypeMachineBuilder[InputProtocol, Core]
    factory: Callable[Concatenate[InputProtocol, Core, FactoryParams], Data]

    def loop(self) -> DataToSelf[InputProtocol, Core, Data]:
        """
        This method does what C{.to(self)} would do, if type signatures could
        be conditional upon identity comparison.
        """
        return DataToSelf(self)

    @overload
    def to(
        self, state: TypifiedState[InputProtocol, Core]
    ) -> DataToNo[InputProtocol, Core, Data]: ...
    @overload
    def to(
        self,
        state: TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams],
    ) -> DataToData[InputProtocol, Core, Data, OtherFactoryParams, OtherData]: ...
    def to(
        self,
        state: (
            TypifiedState[InputProtocol, Core]
            | TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
        ),
    ) -> (
        DataToNo[InputProtocol, Core, Data]
        | DataToData[InputProtocol, Core, Data, OtherFactoryParams, OtherData]
    ):
        """
        Declare a state transition to a new state.
        """
        if isinstance(state, TypifiedState):
            return DataToNo(self, state)
        else:
            assert (
                state is not self
            ), "data-state self-transitions do not take factory parameters to reconstruct their 'data' parameter and thus must be registered with '.loop()' not '.to(...)' to get the right signature"
            return DataToData(self, state)

    def _produce_outputs(
        self,
        impl: Callable[..., object],
        old: (
            TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
            | TypifiedState[InputProtocol, Core]
        ),
        nodata: bool,
    ) -> Iterable[Callable[..., object]]:
        if self is not old:
            yield create_data_output(self.factory)
        yield create_method_output(
            impl, isinstance(old, TypifiedDataState) and not nodata
        )


AnyState: TypeAlias = "TypifiedState[Any, Any] | TypifiedDataState[Any, Any, Any, Any]"


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


def implementMethod(
    method: Callable[..., object],
) -> Callable[..., object]:
    """
    Construct a function for populating in the synthetic provider of the Input
    Protocol to a L{TypeMachineBuilder}.  It should have a signature matching that
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
            [outputs, tracer] = transitioner.transition(method_input)
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
    (per the implementation of L{implementMethod}) takes the 'self' of the
    TypifiedBase instance (i.e. the synthetic protocol implementation) and the
    previous result computed by the former output, which will be None
    initially.
    """

    # sig = _liveSignature(method)
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


@dataclass(frozen=True)
class TypifiedMachine(Generic[InputProtocol, Core]):
    __automat_type__: type[TypifiedBase[Core]]
    __automat_automaton__: Automaton[
        TypifiedState[InputProtocol, Core]
        | TypifiedDataState[InputProtocol, Core, Any, ...],
        str,
        Callable[..., object],
    ]

    def __call__(self, core: Core) -> InputProtocol:
        result: Any = self.__automat_type__(
            core,
            Transitioner(
                self.__automat_automaton__,
                self.__automat_automaton__.initialState,
            ),
        )
        return result

    def asDigraph(self) -> Digraph:
        from ._visualize import makeDigraph

        return makeDigraph(
            self.__automat_automaton__,
            stateAsString=lambda state: state.name,
            inputAsString=lambda input: input,
            outputAsString=lambda output: output.__name__,
        )


@dataclass(eq=False)
class TypeMachineBuilder(Generic[InputProtocol, Core]):
    protocol: ProtocolAtRuntime[InputProtocol]
    core_type: type[Core]
    _automaton: Automaton[
        TypifiedState[InputProtocol, Core]
        | TypifiedDataState[InputProtocol, Core, Any, ...],
        str,
        Callable[..., object],
    ] = field(default_factory=Automaton)
    _initial: bool = True
    _registrars: list[TransitionRegistrar[Any, Any, Any]] = field(
        default_factory=list
    )

    @overload
    def state(self, name: str) -> TypifiedState[InputProtocol, Core]: ...
    @overload
    def state(
        self,
        name: str,
        dataFactory: Callable[Concatenate[InputProtocol, Core, P], Data],
    ) -> TypifiedDataState[InputProtocol, Core, Data, P]: ...
    def state(
        self,
        name: str,
        dataFactory: Callable[Concatenate[InputProtocol, Core, P], Data] | None = None,
    ) -> (
        TypifiedState[InputProtocol, Core]
        | TypifiedDataState[InputProtocol, Core, Data, P]
    ):
        """
        Construct a state.
        """
        if dataFactory is None:
            state = TypifiedState(name, self)
            if self._initial:
                self._initial = False
                self._automaton.initialState = state
            return state
        else:
            assert not self._initial, "initial state cannot require state-specific data"
            return TypifiedDataState(name, self, dataFactory)

    def build(self) -> Callable[[Core], InputProtocol]:
        # incompleteness check

        for registrar in self._registrars:
            registrar._checkComplete()

        namespace = {
            method_name: implementMethod(getattr(self.protocol, method_name))
            for method_name in actuallyDefinedProtocolMethods(self.protocol)
        }

        runtime_type: type[TypifiedBase[Core]] = type(
            f"Typified<{runtime_name(self.protocol)}>",
            tuple([TypifiedBase]),
            namespace,
        )

        return TypifiedMachine(runtime_type, self._automaton)
