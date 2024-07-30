from dataclasses import dataclass
from typing import Callable, Protocol
from unittest import TestCase

from .. import TypeMachineBuilder, pep614


class TestProtocol(Protocol):

    def change(self) -> None:
        "Switch to the other state."

    def value(self) -> int:
        "Give a value specific to the given state."


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
