from dataclasses import dataclass
from typing import Callable, Protocol
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

    first.to(second).upon(TestProtocol.change).returns(None)
    second.to(first).upon(TestProtocol.change).returns(None)

    @pep614(first.loop().upon(TestProtocol.value))
    def firstValue(machine: TestProtocol, core: NoOpCore) -> int:
        return 3

    @pep614(second.loop().upon(TestProtocol.value))
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

        builder = TypeMachineBuilder(Counter, NoOpCore)
        initial = builder.state("initial")
        counting = builder.state("counting", lambda machine, core: Count())
        initial.to(counting).upon(Counter.start).returns(None)

        @pep614(counting.loop().upon(Counter.increment))
        def incf(counter: Counter, core: NoOpCore, count: Count) -> None:
            count.value += 1

        @pep614(counting.to(initial).upon(Counter.stop))
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

    def test_incompleteTransitionDefinition(self) -> None:
        builder = TypeMachineBuilder(SimpleProtocol, NoOpCore)
        sample = builder.state("sample")
        sample.loop().upon(SimpleProtocol.method)  # oops, no '.returns(None)'
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
            stuff: list[str]

        initial = builder.state("initial")
        counting = builder.state("counting", lambda proto, core: Data1(1))
        appending = builder.state("appending", lambda proto, core: Data2([]))

        initial.upon(TestProtocol.change).to(counting).returns(None)

        @pep614(counting.upon(TestProtocol.value).loop())
        def countup(p: TestProtocol, c: NoOpCore, d: Data1) -> int:
            d.value *= 2
            return d.value

        counting.to(appending).upon(TestProtocol.change).returns(None)

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
        toState = initial.to(data)

        # 'assertions' in the form of expected type errors:
        uponInput = toState.upon(TestProtocol.change)  # type:ignore[arg-type]
        uponInput.returns(None)
        toState2 = data.to(data2)
        uponInput2 = toState2.upon(TestProtocol.change)  # type:ignore[arg-type]
        uponInput2.returns(None)

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
