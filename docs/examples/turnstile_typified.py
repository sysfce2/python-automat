from typing import Protocol

from automat import TypifiedBuilder

class Coin:
    "A token conveying value."

class Lock:
    "A sample I/O device."

    def engage(self):
        print("Locked.")

    def disengage(self):
        print("Unlocked.")


class Turnstile(Protocol):
    def arm_turned(self) -> None:
        "The arm was turned."

    def fare_paid(self, coin: Coin) -> None:
        "The fare was paid."

builder = TypifiedBuilder(Turnstile, Lock)

locked = builder.state("Locked")
unlocked = builder.state("Unlocked")

@locked.to(unlocked).upon(Turnstile.fare_paid)
def pay(self: Turnstile, lock: Lock, coin: Coin) -> None:
    lock.disengage()

@locked.loop().upon(Turnstile.arm_turned)
def block(self: Turnstile, lock: Lock) -> None:
    print("**Clunk!**  The turnstile doesn't move.")

@unlocked.to(locked).upon(Turnstile.arm_turned)
def turn(self: Turnstile, lock: Lock) -> None:
    lock.engage()

TurnstileMachine = builder.build()
machine = TurnstileMachine(Lock())
machine.arm_turned()
machine.fare_paid(Coin())
machine.arm_turned()
machine.arm_turned()

