# -*- test-case-name: automat._test.test_type_based -*-
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Iterable,
    Literal,
    Protocol,
    TypeVar,
    overload,
)

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


class AlreadyBuiltError(Exception):
    """
    The :class:`TypeMachine` is already built, and thus can no longer be
    modified.
    """


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

    Type parameter P: the precise signature of the decorated implementation
    callable.

    Type parameter P1: the precise signature of the input method from the
    outward-facing state-machine protocol.

    Type parameter R: the return type of both the protocol method and the input
    method.
    """

    _signature: Callable[P1, R]
    _old: AnyState
    _new: AnyState
    _nodata: bool = False
    _callback: Callable[P, R] | None = None

    def __post_init__(self) -> None:
        self._old.builder._registrars.append(self)

    def __call__(self, impl: Callable[P, R]) -> Callable[P, R]:
        """
        Finalize it with C{__call__} to indicate that there is an
        implementation to the transition, which can be treated as an output.
        """
        if self._callback is not None:
            raise AlreadyBuiltError(
                f"already registered transition from {self._old.name!r} to {self._new.name!r}"
            )
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

        def constant(*args: object, **kwargs: object) -> R:
            return result

        constant.__name__ = f"returns({result})"
        self(constant)

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


@dataclass
class UponFromNo(Generic[InputProtocol, Core, P, R]):
    """
    Type parameter P: the signature of the input method.
    """

    old: (
        TypifiedState[InputProtocol, Core]
        | TypifiedDataState[InputProtocol, Core, Any, ...]
    )
    input: Callable[Concatenate[InputProtocol, P], R]

    @overload
    def to(
        self, state: TypifiedState[InputProtocol, Core]
    ) -> TransitionRegistrar[Concatenate[InputProtocol, Core, P], P, R]: ...
    @overload
    def to(
        self,
        state: TypifiedDataState[InputProtocol, Core, OtherData, P],
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, P],
        Concatenate[InputProtocol, P],
        R,
    ]: ...
    def to(
        self,
        state: (
            TypifiedState[InputProtocol, Core]
            | TypifiedDataState[InputProtocol, Core, Any, P]
        ),
    ) -> (
        TransitionRegistrar[Concatenate[InputProtocol, Core, P], P, R]
        | TransitionRegistrar[
            Concatenate[InputProtocol, Core, P],
            Concatenate[InputProtocol, P],
            R,
        ]
    ):
        """
        Declare a state transition to a new state.
        """
        return TransitionRegistrar(self.input, self.old, state, True)

    def loop(self) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, P],
        Concatenate[InputProtocol, P],
        R,
    ]:
        return TransitionRegistrar(self.input, self.old, self.old, True)


@dataclass
class UponFromData(Generic[InputProtocol, Core, P, R, Data]):
    """
    Type parameter P: the signature of the input method.
    """

    old: TypifiedDataState[InputProtocol, Core, Data, ...]
    input: Callable[Concatenate[InputProtocol, P], R]

    @overload
    def to(
        self, state: TypifiedState[InputProtocol, Core]
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, Data, P], Concatenate[InputProtocol, P], R
    ]: ...
    @overload
    def to(
        self,
        state: TypifiedDataState[InputProtocol, Core, OtherData, P],
    ) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, Data, P],
        Concatenate[InputProtocol, P],
        R,
    ]: ...
    def to(
        self,
        state: (
            TypifiedState[InputProtocol, Core]
            | TypifiedDataState[InputProtocol, Core, Any, P]
        ),
    ) -> (
        TransitionRegistrar[Concatenate[InputProtocol, Core, P], P, R]
        | TransitionRegistrar[
            Concatenate[InputProtocol, Core, Data, P],
            Concatenate[InputProtocol, P],
            R,
        ]
    ):
        """
        Declare a state transition to a new state.
        """
        return TransitionRegistrar(self.input, self.old, state)

    def loop(self) -> TransitionRegistrar[
        Concatenate[InputProtocol, Core, Data, P],
        Concatenate[InputProtocol, P],
        R,
    ]:
        return TransitionRegistrar(self.input, self.old, self.old)


@dataclass(frozen=True)
class TypifiedState(Generic[InputProtocol, Core]):
    name: str
    builder: TypeMachineBuilder[InputProtocol, Core] = field(repr=False)

    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R]
    ) -> UponFromNo[InputProtocol, Core, P, R]:
        self.builder._checkMembership(input)
        return UponFromNo(self, input)

    def _produce_outputs(
        self,
        impl: Callable[..., object],
        old: (
            TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
            | TypifiedState[InputProtocol, Core]
        ),
        nodata: bool = False,
    ) -> Iterable[SomeOutput]:
        yield MethodOutput(impl, isinstance(old, TypifiedDataState))


@dataclass(frozen=True)
class TypifiedDataState(Generic[InputProtocol, Core, Data, FactoryParams]):
    name: str
    builder: TypeMachineBuilder[InputProtocol, Core] = field(repr=False)
    factory: Callable[Concatenate[InputProtocol, Core, FactoryParams], Data]

    @overload
    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R]
    ) -> UponFromData[InputProtocol, Core, P, R, Data]: ...
    @overload
    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R], nodata: Literal[False]
    ) -> UponFromData[InputProtocol, Core, P, R, Data]: ...
    @overload
    def upon(
        self, input: Callable[Concatenate[InputProtocol, P], R], nodata: Literal[True]
    ) -> UponFromNo[InputProtocol, Core, P, R]: ...
    def upon(
        self,
        input: Callable[Concatenate[InputProtocol, P], R],
        nodata: bool = False,
    ) -> (
        UponFromData[InputProtocol, Core, P, R, Data]
        | UponFromNo[InputProtocol, Core, P, R]
    ):
        self.builder._checkMembership(input)
        if nodata:
            return UponFromNo(self, input)
        else:
            return UponFromData(self, input)

    def _produce_outputs(
        self,
        impl: Callable[..., object],
        old: (
            TypifiedDataState[InputProtocol, Core, OtherData, OtherFactoryParams]
            | TypifiedState[InputProtocol, Core]
        ),
        nodata: bool,
    ) -> Iterable[SomeOutput]:
        if self is not old:
            yield DataOutput(self.factory)
        yield MethodOutput(impl, isinstance(old, TypifiedDataState) and not nodata)


AnyState: TypeAlias = "TypifiedState[Any, Any] | TypifiedDataState[Any, Any, Any, Any]"


@dataclass
class TypifiedInput:
    name: str


class SomeOutput(Protocol):
    """
    A state machine output.
    """

    @property
    def name(self) -> str:
        "read-only name property"

    def __call__(*args: Any, **kwargs: Any) -> Any: ...

    def __hash__(self) -> int:
        "must be hashable"


@dataclass
class TypifiedBase(Generic[Core]):
    __automat_core__: Core
    __automat_transitioner__: Transitioner[
        TypifiedState | TypifiedDataState,
        str,
        SomeOutput,
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
        self: TypifiedBase[Core], *args: object, **kwargs: object
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


@dataclass(frozen=True)
class MethodOutput(Generic[Core]):
    """
    This is the thing that goes into the automaton's outputs list, and thus
    (per the implementation of L{implementMethod}) takes the 'self' of the
    TypifiedBase instance (i.e. the synthetic protocol implementation) and the
    previous result computed by the former output, which will be None
    initially.
    """

    method: Callable[..., Any]
    requires_data: bool

    @property
    def name(self) -> str:
        return f"{self.method.__name__}"

    # sig = _liveSignature(method)
    # if requires_data:
    #     # 0: self, 1: self.__automat_core__, 2: self.__automat_data__
    #     param = list(sig.parameters.values())[2]
    #     ann = param.annotation

    def __call__(
        realself,
        self: TypifiedBase[Core],
        data_at_start: Data,
        *args: object,
        **kwargs: object,
    ) -> object:
        extra_args = [self, self.__automat_core__]
        if realself.requires_data:
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
        return realself.method(*extra_args, *args, **kwargs)


@dataclass(frozen=True)
class DataOutput(Generic[Data]):
    """
    Construct an output for the given data objects.
    """

    data_factory: Callable[..., Data]

    @property
    def name(self) -> str:
        return f"data:{self.data_factory.__name__}"

    def __call__(
        realself,
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
            new_data = realself.data_factory(
                self, self.__automat_core__, *args, **kwargs
            )
            self.__automat_data__ = new_data
            return new_data
        finally:
            self.__automat_initializing_data__ = False


@dataclass(frozen=True)
class TypifiedMachine(Generic[InputProtocol, Core]):
    __automat_type__: type[TypifiedBase[Core]]
    __automat_automaton__: Automaton[
        TypifiedState[InputProtocol, Core]
        | TypifiedDataState[InputProtocol, Core, Any, ...],
        str,
        SomeOutput,
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
            outputAsString=lambda output: output.name,
        )


@dataclass(eq=False)
class TypeMachineBuilder(Generic[InputProtocol, Core]):
    protocol: ProtocolAtRuntime[InputProtocol]
    core_type: type[Core]
    _automaton: Automaton[
        TypifiedState[InputProtocol, Core]
        | TypifiedDataState[InputProtocol, Core, Any, ...],
        str,
        SomeOutput,
    ] = field(default_factory=Automaton, repr=False)
    _initial: bool = True
    _registrars: list[TransitionRegistrar[Any, Any, Any]] = field(default_factory=list)
    _built: bool = False

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
        if self._built:
            raise AlreadyBuiltError(
                "Cannot add states to an already-built state machine."
            )
        if dataFactory is None:
            state = TypifiedState(name, self)
            if self._initial:
                self._initial = False
                self._automaton.initialState = state
            return state
        else:
            assert not self._initial, "initial state cannot require state-specific data"
            return TypifiedDataState(name, self, dataFactory)

    def build(self) -> TypifiedMachine[InputProtocol, Core]:
        """
        Create a :class:`TypifiedMachine`, and prevent further modification to
        the state machine being built.
        """
        # incompleteness check
        if self._built:
            raise AlreadyBuiltError("Cannot build a state machine twice.")
        self._built = True

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

    def _checkMembership(self, input: Callable[..., object]) -> None:
        """
        Ensure that ``input`` is a valid member function of the input protocol,
        not just a function that happens to take the right first argument.
        """
        if (checked := getattr(self.protocol, input.__name__, None)) is not input:
            raise ValueError(
                f"{input.__qualname__} is not a member of {self.protocol.__module__}.{self.protocol.__name__}"
            )
