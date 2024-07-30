from typing import Protocol
from unittest import TestCase

from .. import TypeMachineBuilder, pep614

class TypeMachineTests(TestCase):

    def test_oneTransition(self) -> None:

        class TestProtocol(Protocol):

            def change(self) -> None:
                "Switch to the other state."

            def value(self) -> int:
                "Give a value specific to the given state."

        class NoOpCore:
            "Just an object, you know?"

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

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())

        self.assertEqual(machine.value(), 3)
        machine.change()
        self.assertEqual(machine.value(), 4)
        self.assertEqual(machine.value(), 4)
        machine.change()
        self.assertEqual(machine.value(), 3)
