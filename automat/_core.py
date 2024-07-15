# -*- test-case-name: automat._test.test_core -*-

"""
A core state-machine abstraction.

Perhaps something that could be replaced with or integrated into machinist.
"""
from __future__ import annotations
import sys
from itertools import chain
from typing import Generic, Sequence, TypeVar, Callable

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

_NO_STATE = "<no state>"


class NoTransition(Exception):
    """
    A finite state machine in C{state} has no transition for C{symbol}.

    @param state: the finite state machine's state at the time of the
        illegal transition.

    @param symbol: the input symbol for which no transition exists.
    """

    def __init__(self, state, symbol):
        self.state = state
        self.symbol = symbol
        super(Exception, self).__init__(
            "no transition for {} in {}".format(symbol, state)
        )


State = TypeVar("State")
Input = TypeVar("Input")
Output = TypeVar("Output")


class Automaton(Generic[State, Input, Output]):
    """
    A declaration of a finite state machine.

    Note that this is not the machine itself; it is immutable.
    """

    def __init__(self, initial: State | None = None) -> None:
        """
        Initialize the set of transitions and the initial state.
        """
        if initial is None:
            initial = _NO_STATE  # type:ignore[assignment]
        assert initial is not None
        self._initialState: State = initial
        self._transitions: set[tuple[State, Input, State, Sequence[Output]]] = set()
        self._unhandledTransition = None

    @property
    def initialState(self):
        """
        Return this automaton's initial state.
        """
        return self._initialState

    @initialState.setter
    def initialState(self, state):
        """
        Set this automaton's initial state.  Raises a ValueError if
        this automaton already has an initial state.
        """

        if self._initialState is not _NO_STATE:
            raise ValueError(
                "initial state already set to {}".format(self._initialState)
            )

        self._initialState = state

    def addTransition(
        self,
        inState: State,
        inputSymbol: Input,
        outState: State,
        outputSymbols: tuple[Output],
    ):
        """
        Add the given transition to the outputSymbol. Raise ValueError if
        there is already a transition with the same inState and inputSymbol.
        """
        # keeping self._transitions in a flat list makes addTransition
        # O(n^2), but state machines don't tend to have hundreds of
        # transitions.
        for anInState, anInputSymbol, anOutState, _ in self._transitions:
            if anInState == inState and anInputSymbol == inputSymbol:
                raise ValueError(
                    "already have transition from {} via {}".format(
                        inState, inputSymbol
                    )
                )
        self._transitions.add((inState, inputSymbol, outState, tuple(outputSymbols)))

    def unhandledTransition(self, outState, outputSymbols):
        self._unhandledTransition = (outState, outputSymbols)

    def allTransitions(self):
        """
        All transitions.
        """
        return frozenset(self._transitions)

    def inputAlphabet(self):
        """
        The full set of symbols acceptable to this automaton.
        """
        return {
            inputSymbol
            for (inState, inputSymbol, outState, outputSymbol) in self._transitions
        }

    def outputAlphabet(self):
        """
        The full set of symbols which can be produced by this automaton.
        """
        return set(
            chain.from_iterable(
                outputSymbols
                for (inState, inputSymbol, outState, outputSymbols) in self._transitions
            )
        )

    def states(self) -> frozenset[State]:
        """
        All valid states; "Q" in the mathematical description of a state
        machine.
        """
        return frozenset(
            chain.from_iterable(
                (inState, outState)
                for (inState, inputSymbol, outState, outputSymbol) in self._transitions
            )
        )

    def outputForInput(
        self, inState: State, inputSymbol: Input
    ) -> tuple[State, list[Output]]:
        """
        A 2-tuple of (outState, outputSymbols) for inputSymbol.
        """
        for anInState, anInputSymbol, outState, outputSymbols in self._transitions:
            if (inState, inputSymbol) == (anInState, anInputSymbol):
                return (outState, list(outputSymbols))
        if self._unhandledTransition is None:
            raise NoTransition(state=inState, symbol=inputSymbol)
        return self._unhandledTransition


OutputTracer = Callable[[Output], None]
Tracer: TypeAlias = "Callable[[State, Input, State], OutputTracer[Output] | None]"


class Transitioner(Generic[State, Input, Output]):
    """
    The combination of a current state and an L{Automaton}.
    """

    def __init__(self, automaton: Automaton[State, Input, Output], initialState: State):
        self._automaton: Automaton[State, Input, Output] = automaton
        self._state: State = initialState
        self._tracer: Tracer[State, Input, Output] | None = None

    def setTrace(self, tracer: Tracer[State, Input, Output] | None) -> None:
        self._tracer = tracer

    def transition(
        self, inputSymbol: Input
    ) -> tuple[Sequence[Output], OutputTracer[Output] | None]:
        """
        Transition between states, returning any outputs.
        """
        outState, outputSymbols = self._automaton.outputForInput(
            self._state, inputSymbol
        )
        outTracer = None
        if self._tracer:
            outTracer = self._tracer(self._state, inputSymbol, outState)
        self._state = outState
        return (outputSymbols, outTracer)
