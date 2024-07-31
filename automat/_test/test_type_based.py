from dataclasses import dataclass
from typing import Callable, List, Protocol
from unittest import TestCase

from .. import TypeMachineBuilder, pep614


class TestProtocol(Protocol):

    def change(self) -> None:
        "Switch to the other state."

    def value(self) -> int:
        "Give a value specific to the given state."


class ArgTaker(Protocol):
    def takeSomeArgs(self, arg1: int = 0, arg2: str = "") -> None:
        pass


class NoOpCore:
    "Just an object, you know?"


def buildTestBuilder() -> Callable[[NoOpCore], TestProtocol]:
    builder = TypeMachineBuilder(TestProtocol, NoOpCore)
    first = builder.state("first")
    second = builder.state("second")

    first.upon(TestProtocol.change).to(second).returns(None)
    second.upon(TestProtocol.change).to(first).returns(None)

    @pep614(first.upon(TestProtocol.value).loop())
    def firstValue(machine: TestProtocol, core: NoOpCore) -> int:
        return 3

    @pep614(second.upon(TestProtocol.value).loop())
    def secondValue(machine: TestProtocol, core: NoOpCore) -> int:
        return 4

    return builder.build()


machineFactory = buildTestBuilder()


def needsSomething(proto: TestProtocol, core: NoOpCore, value: str) -> int:
    "we need data to build this state"
    return 3


def needsNothing(proto: ArgTaker, core: NoOpCore) -> str:
    return "state-specific data"


class SimpleProtocol(Protocol):
    def method(self) -> None:
        "A method"


class Counter(Protocol):
    def start(self) -> None:
        "enter the counting state"

    def increment(self) -> None:
        "increment the counter"

    def stop(self) -> int:
        "stop"


@dataclass
class Count:
    value: int = 0


class TypeMachineTests(TestCase):

    def test_oneTransition(self) -> None:

        machine = machineFactory(NoOpCore())

        self.assertEqual(machine.value(), 3)
        machine.change()
        self.assertEqual(machine.value(), 4)
        self.assertEqual(machine.value(), 4)
        machine.change()
        self.assertEqual(machine.value(), 3)

    def test_stateSpecificData(self) -> None:

        builder = TypeMachineBuilder(Counter, NoOpCore)
        initial = builder.state("initial")
        counting = builder.state("counting", lambda machine, core: Count())
        initial.upon(Counter.start).to(counting).returns(None)

        @pep614(counting.upon(Counter.increment).loop())
        def incf(counter: Counter, core: NoOpCore, count: Count) -> None:
            count.value += 1

        @pep614(counting.upon(Counter.stop).to(initial))
        def finish(counter: Counter, core: NoOpCore, count: Count) -> int:
            return count.value

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        machine.start()
        machine.increment()
        machine.increment()
        self.assertEqual(machine.stop(), 2)
        machine.start()
        machine.increment()
        self.assertEqual(machine.stop(), 1)

    def test_stateSpecificDataWithoutData(self) -> None:
        """
        To facilitate common implementations of transition behavior methods,
        sometimes you want to implement a transition within a data state
        without taking a data parameter.  To do this, pass the 'nodata=True'
        parameter to 'upon'.
        """
        builder = TypeMachineBuilder(Counter, NoOpCore)
        initial = builder.state("initial")
        counting = builder.state("counting", lambda machine, core: Count())
        startCalls = []

        @pep614(initial.upon(Counter.start).to(counting))
        @pep614(counting.upon(Counter.start, nodata=True).loop())
        def start(counter: Counter, core: NoOpCore) -> None:
            startCalls.append("started!")

        @pep614(counting.upon(Counter.increment).loop())
        def incf(counter: Counter, core: NoOpCore, count: Count) -> None:
            count.value += 1

        @pep614(counting.upon(Counter.stop).to(initial))
        def finish(counter: Counter, core: NoOpCore, count: Count) -> int:
            return count.value

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        machine.start()
        self.assertEqual(len(startCalls), 1)
        machine.start()
        self.assertEqual(len(startCalls), 2)
        machine.increment()
        self.assertEqual(machine.stop(), 1)

    def test_incompleteTransitionDefinition(self) -> None:
        builder = TypeMachineBuilder(SimpleProtocol, NoOpCore)
        sample = builder.state("sample")
        sample.upon(SimpleProtocol.method).loop()  # oops, no '.returns(None)'
        with self.assertRaises(ValueError) as raised:
            builder.build()
        self.assertIn(
            "incomplete transition from sample to sample upon SimpleProtocol.method",
            str(raised.exception),
        )

    def test_dataToData(self) -> None:
        builder = TypeMachineBuilder(TestProtocol, NoOpCore)

        @dataclass
        class Data1:
            value: int

        @dataclass
        class Data2:
            stuff: List[str]

        initial = builder.state("initial")
        counting = builder.state("counting", lambda proto, core: Data1(1))
        appending = builder.state("appending", lambda proto, core: Data2([]))

        initial.upon(TestProtocol.change).to(counting).returns(None)

        @pep614(counting.upon(TestProtocol.value).loop())
        def countup(p: TestProtocol, c: NoOpCore, d: Data1) -> int:
            d.value *= 2
            return d.value

        counting.upon(TestProtocol.change).to(appending).returns(None)

        @pep614(appending.upon(TestProtocol.value).loop())
        def appendup(p: TestProtocol, c: NoOpCore, d: Data2) -> int:
            d.stuff.extend("abc")
            return len(d.stuff)

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        machine.change()
        self.assertEqual(machine.value(), 2)
        self.assertEqual(machine.value(), 4)
        machine.change()
        self.assertEqual(machine.value(), 3)
        self.assertEqual(machine.value(), 6)

    def test_dataFactoryArgs(self) -> None:
        """
        Any data factory that takes arguments will constrain the allowed
        signature of all protocol methods that transition into that state.
        """
        builder = TypeMachineBuilder(TestProtocol, NoOpCore)
        initial = builder.state("initial")
        data = builder.state("data", needsSomething)
        data2 = builder.state("data2", needsSomething)
        # toState = initial.to(data)

        # 'assertions' in the form of expected type errors:
        # (no data -> data)
        uponNoData = initial.upon(TestProtocol.change)
        uponNoData.to(data)  # type:ignore[arg-type]

        # (data -> data)
        uponData = data.upon(TestProtocol.change)
        uponData.to(data2)  # type:ignore[arg-type]

    def test_dataFactoryNoArgs(self) -> None:
        """
        Inverse of C{test_dataFactoryArgs} where the data factory specifically
        does I{not} take arguments, but the input specified does.
        """
        builder = TypeMachineBuilder(ArgTaker, NoOpCore)
        initial = builder.state("initial")
        data = builder.state("data", needsNothing)
        (
            initial.upon(ArgTaker.takeSomeArgs)
            .to(data)  # type:ignore[arg-type]
            .returns(None)
        )

    def test_reentrancy(self) -> None:
        """
        During the execution of a transition behavior implementation function,
        you may invoke other methods on your state machine.  However, the
        execution of the behavior of those methods will be deferred until the
        current behavior method is done executing.  In order to implement that
        deferral, we restrict the set of methods that can be invoked to those
        that return None.

        @note: it may be possible to implement deferral via Awaitables or
            Deferreds later, but we are starting simple.
        """

        class SomeMethods(Protocol):
            def start(self) -> None:
                "Start the machine."

            def later(self) -> None:
                "Do some deferrable work."

        builder = TypeMachineBuilder(SomeMethods, NoOpCore)

        initial = builder.state("initial")
        second = builder.state("second")

        order = []

        @pep614(initial.upon(SomeMethods.start).to(second))
        def startup(methods: SomeMethods, core: NoOpCore) -> None:
            order.append("startup")
            methods.later()
            order.append("startup done")

        @pep614(second.upon(SomeMethods.later).loop())
        def later(methods: SomeMethods, core: NoOpCore) -> None:
            order.append("later")

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        machine.start()
        self.assertEqual(order, ["startup", "startup done", "later"])

    def test_reentrancyNotNoneError(self) -> None:
        class SomeMethods(Protocol):
            def start(self) -> None:
                "Start the machine."

            def later(self) -> int:
                "Do some deferrable work."

        builder = TypeMachineBuilder(SomeMethods, NoOpCore)

        initial = builder.state("initial")
        second = builder.state("second")

        order = []

        @pep614(initial.upon(SomeMethods.start).to(second))
        def startup(methods: SomeMethods, core: NoOpCore) -> None:
            order.append("startup")
            methods.later()
            order.append("startup done")

        @pep614(second.upon(SomeMethods.later).loop())
        def later(methods: SomeMethods, core: NoOpCore) -> int:
            order.append("later")
            return 3

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        with self.assertRaises(RuntimeError):
            machine.start()
        self.assertEqual(order, ["startup"])
        # We do actually do the state transition, which happens *before* the
        # output is generated; TODO: maybe we should have exception handling
        # that transitions into an error state that requires explicit recovery?
        self.assertEqual(machine.later(), 3)
        self.assertEqual(order, ["startup", "later"])
