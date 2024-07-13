# -*- test-case-name: automat._test.test_typical -*-
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from inspect import Parameter, Signature, signature
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    NoReturn,
    Optional,
    Protocol,
    Sequence,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from ._core import Automaton, Transitioner

SelfCon = TypeVar("SelfCon", contravariant=True)
InputsProtoInv = TypeVar("InputsProtoInv")
InputsProtoCon = TypeVar("InputsProtoCon", contravariant=True)
SharedCoreCo = TypeVar("SharedCoreCo", covariant=True)
SharedCoreCon = TypeVar("SharedCoreCon", contravariant=True)
InputsProto = TypeVar("InputsProto", covariant=True)
PrivateProto = TypeVar("PrivateProto", covariant=True)
UserStateType = object
SharedCore = TypeVar("SharedCore")
OutputResult = TypeVar("OutputResult")
SelfA = TypeVar("SelfA")
SelfB = TypeVar("SelfB")
R = TypeVar("R")
T = TypeVar("T")
OutputCallable = TypeVar("OutputCallable", bound=Callable[..., Any])


if sys.version_info >= (3, 10):
    from typing import Concatenate, ParamSpec, get_type_hints

else:
    from typing_extensions import Concatenate, ParamSpec, get_type_hints
P = ParamSpec("P")
ThisInputArgs = ParamSpec("ThisInputArgs")
FlexibleStateFactory = Union[
    # There are unfortunately too many different ways to specify the state
    # factory.
    Callable[..., T],
]
EnterMethod = Optional[Callable[[], FlexibleStateFactory[T]]]


@dataclass
class Enter(Generic[T]):
    """
    Type annotation instruction to enter the next state.
    """

    state: type[T]


class ProtocolAtRuntime(Protocol[InputsProto]):
    # __name__: str # https://github.com/python/mypy/issues/12976
    def __call__(self) -> InputsProto:
        ...


def _name(x: ProtocolAtRuntime[T]) -> str:
    return x.__name__  # type:ignore[attr-defined]


class CouldNotFindAutoParam(RuntimeError):
    """
    Raised when an automatically-populated parameter cannot be found.
    """


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


class ParameterBuilder(Protocol):
    def __call__(
        self,
        syntheticSelf: _TypicalInstance[InputsProto, SharedCore],
        sharedCore: object,
        existingStateCluster: Mapping[str, object],
    ) -> object:
        ...


class StateBuilder(Protocol):
    """
    A L{StateBuilder} is a factory function which can create a State object
    from a collection of inputs.
    """

    def __call__(
        self,
        syntheticSelf: _TypicalInstance[InputsProto, SharedCore],
        sharedCore: object,
        existingStateCluster: Mapping[str, object],
        args: Tuple[object, ...],
        kwargs: Dict[str, object],
    ) -> object:
        """
        @param syntheticSelf: The L{_TypicalInstance} that contains the
            collection of state objects and the state core.

        @param sharedCore: The state core for the state machine.

        @param existingStateCluster: pass

        @param args: The arguments passed to the input.

        @param kwargs: The keyword arguments passed to the input.
        """


def _getOtherState(name: str) -> ParameterBuilder:
    def _otherState(
        syntheticSelf: _TypicalInstance[InputsProto, SharedCore],
        sharedCore: object,
        existingStateCluster: Mapping[str, object],
    ) -> object:
        return existingStateCluster[name]

    return _otherState


def _getCore(
    syntheticSelf: _TypicalInstance[InputsProto, SharedCore],
    sharedCore: object,
    existingStateCluster: Mapping[str, object],
) -> object:
    return sharedCore


def _getCoreAttribute(attr: str) -> ParameterBuilder:
    # TODO: automatically getting attributes from the core object rather than
    # the input signature is probably just a bad idea, way too much magic.  it
    # exists because the "state just constructed" hook of __post_init__ (or
    # __init__ sometimes I guess) is an awkward way of populating
    # derived-but-cached attributes.  But it would probably be best to just get
    # rid of these sematics and see if there's some explicit / opt-in version
    # of this we could add as an API later.
    def _coreGetter(
        syntheticSelf: _TypicalInstance[InputsProto, SharedCore],
        sharedCore: object,
        existingStateCluster: Mapping[str, object],
    ) -> object:
        return getattr(sharedCore, attr)

    return _coreGetter


def _getSynthSelf(
    syntheticSelf: _TypicalInstance[InputsProto, SharedCore],
    sharedCore: object,
    existingStateCluster: Mapping[str, object],
) -> object:
    return syntheticSelf


def _stateBuilder(
    inputSignature: Signature,
    stateFactorySignature: Signature,
    stateFactory: Callable[P, Any],
    suppliers: list[tuple[str, ParameterBuilder]] = [],
) -> StateBuilder:
    # the wanted parameters are the parameters requested by the state factory,
    # which is to say e.g. the dataclass's parameters
    wanted = frozenset(stateFactorySignature.parameters)

    def _(
        syntheticSelf: _TypicalInstance[InputsProto, SharedCore],
        sharedCore: object,
        existingStateCluster: Mapping[str, object],
        args: Tuple[object, ...],
        kwargs: Dict[str, object],
    ) -> object:
        boundArgs = inputSignature.bind(*args, **kwargs).arguments

        # we are kicking out the arguments passed to the input method which are
        # *not* wanted by the underlying state factory.
        for unwanted in frozenset(boundArgs) - wanted:
            del boundArgs[unwanted]

        for (extraParamName, extraParamFactory) in suppliers:
            boundArgs[extraParamName] = extraParamFactory(
                syntheticSelf, sharedCore, existingStateCluster
            )
        return stateFactory(**boundArgs)

    return _


def _buildParameterBuilders(
    stateFactorySignature: Signature,
    transitionSignature: Signature,
    stateFactories: Dict[str, Callable[..., UserStateType]],
    sharedCoreType: type[object],
    inputProtocols: frozenset[ProtocolAtRuntime[object]],
) -> Iterable[tuple[str, ParameterBuilder]]:
    """
    Construct an iterable of (parameter name, L{ParameterBuilder}) for all the
    parameters required by the factory function that creates a state object,
    that need to be I{implicitly} supplied during the given state-transition
    method, because they will not be passed to the input function.

    This is called only during L{TypicalBuilder.buildClass} and is one phase of
    a multi-step process, split out for legibility.

    @param stateFactorySignature: The L{Signature} describing the callable that
        will construct the state object.  i.e.: this is something decorated by
        L{TypicalBuilder.state}.

    @param transitionSignature: The L{Signature} describing the callable that
        will be invoked as an input.  i.e.: this is the signature of something
        decorated by L{TypicalBuilder.handle}, the signature of a method on the
        C{_stateProtocol} attribute of L{TypicalBuilder}.

    @param stateFactories: A dictionary mapping state-name to all the state
        factories used by the given L{TypicalBuilder}.

    @param sharedCoreType: the type of the state core associated with the
        L{TypicalBuilder} we are building.

    @todo: C{sharedCoreType}'s type is somewhat ambiguous, as a type some places
        and a callable others; we should tighten that up to make it more
        consistent.

    @param inputProtocols: all of the input protocols for the state machine we
        are building, both public and private.
    """

    factoryNeeds = set(stateFactorySignature.parameters)
    transitionSupplies = set(transitionSignature.parameters)
    notSuppliedParams = factoryNeeds - transitionSupplies
    for maybeTypeMismatch in factoryNeeds & transitionSupplies:
        fromTransition = transitionSignature.parameters[maybeTypeMismatch].annotation
        fromFactory = stateFactorySignature.parameters[maybeTypeMismatch].annotation
        if fromTransition != fromFactory:
            fromFactoryDefault = stateFactorySignature.parameters[
                maybeTypeMismatch
            ].default
            if fromFactoryDefault == Parameter.empty:
                notSuppliedParams.add(maybeTypeMismatch)

    for nameForParameterNotSuppliedByTransitionInputs in notSuppliedParams:
        # These are the parameters we will need to supply.
        notSuppliedByTransition = stateFactorySignature.parameters[
            nameForParameterNotSuppliedByTransitionInputs
        ]
        parameterType = notSuppliedByTransition.annotation
        yield nameForParameterNotSuppliedByTransitionInputs, _oneParameterBuilder(
            nameForParameterNotSuppliedByTransitionInputs,
            parameterType,
            stateFactories,
            sharedCoreType,
            inputProtocols,
        )


def _oneParameterBuilder(
    nameForParameterNotSuppliedByTransitionInputs: str,
    parameterType: Any,
    stateFactories: Dict[str, Callable[..., UserStateType]],
    sharedCoreType: object,
    inputProtocols: frozenset[ProtocolAtRuntime[object]],
) -> ParameterBuilder:
    """
    Construct a single implicit parameter builder.

    @see: L{_buildParameterBuilders}
    """
    if parameterType.__name__ in stateFactories:
        # If the class name of the parameter's type exactly matches the name of
        # another state type within this state machine, return the
        # already-created state.

        # FIXME: this check is too loose, and checks only the class's direct
        # name, not its module or anything else.
        return _getOtherState(parameterType.__name__)
    elif parameterType is sharedCoreType:
        # If the parameter type is the state core type, pass the state core
        # along directly.
        return _getCore
    elif parameterType in inputProtocols:
        # If the parameter type is exactly one of the input Protocols (whether
        # the public outward-facing one built by the typical machine or one of
        # the private ones passed to L{TypicalBuilder._privateProtocols}), pass
        # the 'synthetic self' built internally which conforms to all the input protocols at
        # once.
        return _getSynthSelf
    else:
        # If the name of the parameter exaclty matches one of the attributes on
        # the state core, pass that attribute along.

        # FIXME: this is probably just too much magic at a distance, you can
        # just as easily ask for the state core itself and access its
        # attributes.  Also, you can't take a default parameter, since it will
        # be clobbered by the exception that comes along with attempting to get
        # the attribute from the core, even though a default was supplied; the
        # Parameter.empty check is supposed to catch that, but it doesn't for
        # dataclasses, it seems.
        return _getCoreAttribute(nameForParameterNotSuppliedByTransitionInputs)


def _buildStateBuilder(
    sharedCoreType: type[object],
    stateFactory: Callable[..., Any],
    stateFactories: Dict[str, Callable[..., UserStateType]],
    transitionMethod: Any,
    inputProtocols: frozenset[ProtocolAtRuntime[object]],
) -> StateBuilder:
    """
    We want to build a factory that takes live args/kwargs and translates them
    into a state instance.

    @param transitionMethod: The method from the state-machine protocol, which
        documents its public parameters.
    """
    # TODO: benchmark the generated function, it's probably going to be pretty
    # performance sensitive, and probably switch over to codegen a-la attrs or
    # dataclassess since that will probably be faster.

    # the transition signature is empty / no arguments for the initial state
    # build
    transitionSignature = (
        _liveSignature(transitionMethod)
        if transitionMethod is not None
        else Signature([Parameter("self", Parameter.POSITIONAL_OR_KEYWORD)])
    )
    skipped = iter(transitionSignature.parameters.values())
    next(skipped)
    transitionSignature = transitionSignature.replace(parameters=list(skipped))
    stateFactorySignature = _liveSignature(stateFactory)

    return _stateBuilder(
        transitionSignature,
        stateFactorySignature,
        stateFactory,
        # All the parameters that the transition expects MUST be supplied by
        # the caller; they will be passed along to the factory.  The factory
        # should not supply them in other ways (default values will not be
        # respected, attributes won't be pulled from the state core, etc)
        list(
            _buildParameterBuilders(
                stateFactorySignature,
                transitionSignature,
                stateFactories,
                sharedCoreType,
                inputProtocols,
            )
        ),
    )


_baseMethods = set(dir(Protocol))


def _bindableInputMethod(
    inputMethod: Callable[P, object],
    inputProtocols: frozenset[ProtocolAtRuntime[object]],
    errorState: Callable[..., object],
) -> Callable[..., object]:
    """
    Create a bindable method (i.e. "function for use at class scope") to
    implement a I{state machine input} for the given L{_TypicalInstance}.
    """
    inputMethodName = inputMethod.__name__
    assert inputMethodName != "<lambda>"

    @wraps(inputMethod)
    def method(
        self: _TypicalInstance[InputsProto, SharedCore], *a: P.args, **kw: P.kwargs
    ) -> object:
        oldStateName = self._transitioner._state
        oldStateObject = self._stateCluster[oldStateName]
        [[outputMethodName], tracer] = self._transitioner.transition(inputMethodName)
        newStateName = self._transitioner._state
        # here we need to invoke the output method
        if outputMethodName is None:
            self._stateCluster[newStateName] = errorState()
            raise RuntimeError(
                f"unhandled: state:{oldStateName} input:{inputMethodName}"
            )
        realMethod = getattr(oldStateObject, outputMethodName)
        stateBuilder: StateBuilder = realMethod.__stateBuilder__
        stateEnter = None
        if newStateName not in self._stateCluster:
            newBuilt = stateBuilder(self, self._sharedCore, self._stateCluster, a, kw)
            self._stateCluster[newStateName] = newBuilt
            stateEnter = getattr(newBuilt, "__automat_post_enter__", None)
        shouldStatePersist = (
            oldStateObject.__persistState__  # type:ignore[attr-defined]
        )
        if newStateName != oldStateName and not shouldStatePersist:
            del self._stateCluster[oldStateName]
        if stateEnter is not None:
            stateEnter()
        result = realMethod(*a, **kw)
        return result

    return method


def _bindableCommonMethod(
    inputMethod: Callable[
        Concatenate[_TypicalInstance[InputsProto, SharedCore], P], object
    ],
    impl: Callable[
        Concatenate[
            _TypicalInstance[InputsProto, SharedCore], SharedCore, InputsProto, P
        ],
        object,
    ],
    includePrivate: bool,
) -> Callable[Concatenate[_TypicalInstance[InputsProto, SharedCore], P], object]:
    """
    Create a bindable method (i.e. "function for use at class scope") to
    implement a I{common behavior} across all states of a given
    L{_TypicalInstance}.  Common methods appear to callers as methods.

    However, unlike transition methods which invoke state-specific behavior and
    may transition the state machine, common methods are just like regular
    methods you might define on a class, that are defined on the *outer* state machine.
    """

    @wraps(inputMethod)
    def method(
        self: _TypicalInstance[InputsProto, SharedCore], *a: P.args, **kw: P.kwargs
    ) -> object:
        return impl(
            self,
            self._sharedCore,
            # TODO: includePrivate needs to be present in an @override that
            # more correctly describes the 3rd argument to the input impl as
            # potentially containing a private interface?
            *([self] if includePrivate else []),  # type:ignore[arg-type]
            *a,
            **kw,  # type:ignore[arg-type]
        )

    return method


@dataclass
class _TypicalInstance(Generic[InputsProto, SharedCore]):
    """
    Trivial superclass of state-cluster instances.  To application code,
    appears to be a provider of the C{InputsProto} protocol.  Methods are
    populated below by the logic in L{TypicalBuilder.buildClass}.
    """

    _sharedCore: SharedCore
    _transitioner: Transitioner
    _stateCluster: Dict[str, UserStateType] = field(default_factory=dict)


if TYPE_CHECKING:
    _typeish = type
else:
    _typeish = object


@dataclass
class _TypicalClass(
    Generic[InputsProto, SharedCore, P],
    _typeish,  # Lie about being a type to work around
    # https://github.com/python/mypy/issues/12974
):
    """
    Class-ish object that supplies the implementation of the protocol described
    by L{InputsProto}.  This class's constructor mimics the signature of its
    state-builder function, and it will type-check accordingly.
    """

    _buildCore: Callable[P, SharedCore]
    _initialState: Type[UserStateType]
    _automaton: Automaton
    _realSyntheticType: Type[_TypicalInstance[InputsProto, SharedCore]]
    _inputProtocols: frozenset[ProtocolAtRuntime[object]]
    _initialStateBuilder: StateBuilder

    def __call__(self, *initArgs: P.args, **initKwargs: P.kwargs) -> InputsProto:
        """
        Instantiate the class asociated with this L{_TypicalClass}, producing
        something that appears to be an L{InputsProto}.
        """
        result = self._realSyntheticType(
            sharedCore := self._buildCore(*initArgs, **initKwargs),
            Transitioner(self._automaton, self._initialState.__name__),
        )
        result._stateCluster[result._transitioner._state] = self._initialStateBuilder(
            result, sharedCore, result._stateCluster, initArgs, initKwargs
        )
        return result  # type: ignore

    def __instancecheck__(self, other: object) -> bool:
        """
        A L{_TypicalInstance} is an instance of this L{_TypicalClass} it
        points to this object.
        """
        return isinstance(other, self._realSyntheticType)


class ErrorState:
    """
    This is the default error state.  It has no methods, and so you cannot
    recover by default.
    """

    __persistState__ = False


SharedCoreContra = TypeVar("SharedCoreContra", contravariant=True)


class NextStateFactory(Protocol[P, SharedCoreContra]):
    def __call__(self, core: SharedCoreContra, *args: P.args, **kw: P.kwargs) -> object:
        ...


class Handler(
    Protocol[
        # The inputs protocol.
        InputsProto,
        # The 'self' passed to the input method; i.e. the state-specific class.
        SelfCon,
        # The arguments of the input method.
        ThisInputArgs,
        # The return value of the input method.
        R,
        # The return value of the state-builder method.
        SelfB,
    ]
):
    __automat_input__: Callable[Concatenate[InputsProto, ThisInputArgs], R]
    __automat_buildState__: EnterMethod[SelfB]

    def __call__(
        # We are defining a method that goes on a class, so the "self" is the
        # Handler itself, which doesn't actually get passed.
        notself,
        /,
        self: SelfCon,
        *args: ThisInputArgs.args,
        **kwargs: ThisInputArgs.kwargs,
    ) -> R:
        ...

    @overload
    def __get__(self: T, instance: None, owner: Optional[Type[object]] = None) -> T:
        ...

    @overload
    def __get__(
        self, instance: object, owner: Optional[Type[object]] = None
    ) -> Callable[ThisInputArgs, R]:
        ...


AnyHandler = Handler[Any, Any, Any, Any, Any]


def _stateOutputs(
    stateClass: type[SelfA],
) -> Iterable[tuple[str, str, str, FlexibleStateFactory[object]]]:
    """
    Extract all input-handling methods from a given state class, returning a
    4-tuple of:

        1. the name of the I{output method} from the state class; i.e. the
           method that has actually been defined here.

        2. the name of the I{input method} from the inputs C{Protocol} on the
           state machine

        3. the name of the I{state builder} (as stored in
           L{_TypicalClass._stateBuilders}) to invoke, in order to build the
           state to transition to after the aforementioned state-machine input
           has been handled by the aforementioned state output method.

        4. a L{FlexibleStateFactory} that can construct a state.
    """
    for outputMethodName in dir(stateClass):
        maybeOutputMethod = getattr(stateClass, outputMethodName, None)
        if maybeOutputMethod is None or not hasattr(
            maybeOutputMethod, "__automat_input__"
        ):
            continue

        outputMethod: Handler[Any, SelfA, Any, Any, object] = maybeOutputMethod
        inputMethod = outputMethod.__automat_input__
        enterParameter = outputMethod.__automat_buildState__

        newStateFactory: FlexibleStateFactory[object]
        if enterParameter is not None:
            newStateFactory = enterParameter()
        else:
            newStateFactory = stateClass  # type:ignore[assignment]

        for enterAnnotation in (
            each
            for each in getattr(
                get_type_hints(outputMethod, include_extras=True).get("return"),
                "__metadata__",
                (),
            )
            if isinstance(each, Enter)
        ):
            newStateFactory = enterAnnotation.state
        newStateName: str = newStateFactory.__name__
        yield (
            outputMethodName,
            inputMethod.__name__,
            newStateName,
            newStateFactory,
        )


class _SampleProtocol(Protocol):
    pass


from inspect import getmembers, isfunction

emptyProtocolMethods = frozenset(
    name for name, each in getmembers(_SampleProtocol, isfunction)
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


@dataclass
class TypicalBuilder(Generic[InputsProto, SharedCore, P]):
    """
    Decorator-based interface.
    """

    _stateProtocol: ProtocolAtRuntime[InputsProto]
    _buildCore: Callable[P, SharedCore]
    _privateProtocols: set[ProtocolAtRuntime[object]] = field(default_factory=set)

    # internal state
    _stateClasses: List[Type[object]] = field(default_factory=list)
    _built: bool = False
    _errorState: Type[object] = ErrorState
    _commonMethods: Dict[str, Tuple[Callable[..., Any], bool]] = field(
        default_factory=dict
    )

    def buildClass(self) -> _TypicalClass[InputsProto, SharedCore, P]:
        """
        Transfer state class declarations into underlying state machine.
        """
        if self._built:
            raise RuntimeError("You can only build once, after that use the class")
        self._built = True
        automaton = Automaton()
        automaton.unhandledTransition(self._errorState.__name__, [None])
        stateFactories: Dict[str, Callable[..., UserStateType]] = {}
        allProtocols = frozenset([self._stateProtocol, *self._privateProtocols])

        # TODO: fix this to grab a return annotation or something
        sharedCoreType: type[object] = self._buildCore  # type:ignore[assignment]

        ns: Dict[str, object] = {
            "_stateFactories": stateFactories,
        }
        buildAfterFactories = []
        for eachStateProtocol in [self._stateProtocol, *self._privateProtocols]:
            possibleInputs = actuallyDefinedProtocolMethods(eachStateProtocol)
            for stateClass in [*self._stateClasses, self._errorState]:
                stateName = stateClass.__name__
                stateFactories[stateName] = stateClass
                for (
                    outputName,
                    inputName,
                    newStateName,
                    newStateFactory,
                ) in _stateOutputs(stateClass):
                    output = getattr(stateClass, outputName)
                    if inputName in possibleInputs:
                        automaton.addTransition(
                            stateName, inputName, newStateName, [outputName]
                        )
                        buildAfterFactories.append(
                            (output, sharedCoreType, stateClass, newStateFactory)
                        )
            for eachInput in possibleInputs:
                ns[eachInput] = _bindableInputMethod(
                    getattr(eachStateProtocol, eachInput),
                    allProtocols,
                    self._errorState,
                )
        # stateFactories is built, now time to build the builders

        for (
            output,
            sharedCoreType,
            stateClassName,
            newStateFactory,
        ) in buildAfterFactories:
            output.__stateBuilder__ = _buildStateBuilder(
                sharedCoreType,
                newStateFactory,
                stateFactories,
                output,
                allProtocols,
            )

        # common methods are really only supposed to work for the main / public
        # interface, since the only reason to have them is public-facing.
        commonMethods: dict[str, Callable[..., object]] = {
            commonMethodName: _bindableCommonMethod(
                getattr(self._stateProtocol, commonMethodName),
                commonImpl,
                includePrivate,
            )
            for commonMethodName, (
                commonImpl,
                includePrivate,
            ) in self._commonMethods.items()
        }
        # initial state builder has to take the arguments for the state core's
        # constructor.
        initialStateBuilder = _buildStateBuilder(
            sharedCoreType,
            self._stateClasses[0],
            stateFactories,
            sharedCoreType.__init__,
            allProtocols,
        )
        return _TypicalClass(
            self._buildCore,
            self._stateClasses[0],
            automaton,
            type(
                f"Machine<{_name(self._stateProtocol)}>",
                tuple([_TypicalInstance]),
                {
                    **ns,
                    **commonMethods,
                },
            ),
            allProtocols,
            initialStateBuilder,
        )

    def state(
        self, *, persist: bool = True, error: bool = False
    ) -> Callable[[type[T]], type[T]]:
        """
        Decorate a state class to note that it's a state.

        @param persist: Whether to forget the given state when transitioning
            away from it.
        """

        def _saveStateClass(stateClass: Type[T]) -> Type[T]:
            stateClass.__persistState__ = persist  # type: ignore
            if error:
                self._errorState = stateClass
            else:
                self._stateClasses.append(stateClass)
            return stateClass

        return _saveStateClass

    def handle(
        self,
        input: Callable[Concatenate[InputsProtoInv, ThisInputArgs], R],
        enter: EnterMethod[SelfB] = None,
    ) -> Callable[
        [Callable[Concatenate[SelfA, ThisInputArgs], R]],
        Handler[InputsProtoInv, SelfA, ThisInputArgs, R, SelfB],
    ]:
        """
        Define an input handler.
        """

        def decorator(
            c: OutputCallable,
        ) -> Handler[InputsProtoInv, SelfA, ThisInputArgs, R, SelfB]:
            result: Handler[InputsProtoInv, SelfA, ThisInputArgs, R, SelfB]
            result = c  # type:ignore[assignment]
            other: Callable[Concatenate[InputsProtoInv, ThisInputArgs], R] = input
            result.__automat_input__ = other
            result.__automat_buildState__ = enter
            return result

        return decorator

    @overload
    def common(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
    ) -> Callable[
        [Callable[Concatenate[InputsProto, SharedCore, ThisInputArgs], R]],
        Callable[Concatenate[InputsProto, SharedCore, ThisInputArgs], R],
    ]:
        ...

    @overload
    def common(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
        privateType: ProtocolAtRuntime[PrivateProto],
    ) -> Callable[
        [Callable[Concatenate[InputsProto, SharedCore, PrivateProto, ThisInputArgs], R]],
        Callable[Concatenate[InputsProto, SharedCore, PrivateProto, ThisInputArgs], R],
    ]:
        ...

    def common(
        self,
        input: Callable[Concatenate[SelfA, ThisInputArgs], R],
        privateType: ProtocolAtRuntime[PrivateProto] | None = None,
    ) -> (
        Callable[
            [
                Callable[
                    Concatenate[InputsProto, SharedCore, PrivateProto, ThisInputArgs], R
                ]
            ],
            Callable[
                Concatenate[InputsProto, SharedCore, PrivateProto, ThisInputArgs], R
            ],
        ]
        | Callable[
            [Callable[Concatenate[InputsProto, SharedCore, ThisInputArgs], R]],
            Callable[Concatenate[InputsProto, SharedCore, ThisInputArgs], R],
        ]
    ):
        """
        Implement one of the methods on the public inputs protocol.
        """
        if privateType is not None:
            self._privateProtocols.add(privateType)

        def decorator(f: OutputCallable) -> OutputCallable:
            self._commonMethods[input.__name__] = (f, privateType is not None)
            return f

        return decorator
