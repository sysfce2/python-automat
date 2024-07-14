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

builder = TypifiedBuilder[Turnstile, Lock](Lock)

locked = builder.state("Locked", initial=True)
unlocked = builder.state("Unlocked")

@locked.transition(Turnstile.fare_paid, unlocked)
def pay(self: Turnstile, lock: Lock, coin: Coin) -> None:  # fare_paid's args go here
    lock.disengage()

@locked.transition(Turnstile.arm_turned, locked)
def block(self: Turnstile, lock: Lock) -> None:
    print("**Clunk!**  The turnstile doesn't move.")

@unlocked.transition(Turnstile.arm_turned)
def turn(self: Turnstile, lock: Lock) -> None:
    lock.engage()

TurnstileMachine = machine.build()
