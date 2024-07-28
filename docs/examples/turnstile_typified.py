from typing import Callable, Protocol

from automat import TypifiedBuilder


class Lock:
    "A sample I/O device."

    def engage(self):
        print("Locked.")

    def disengage(self):
        print("Unlocked.")


class Turnstile(Protocol):
    def arm_turned(self) -> None:
        "The arm was turned."

    def fare_paid(self, coin: int) -> None:
        "The fare was paid."


def buildBuilder() -> Callable[[Lock], Turnstile]:
    builder = TypifiedBuilder(Turnstile, Lock)
    locked = builder.state("Locked")
    unlocked = builder.state("Unlocked")

    @locked.to(unlocked).upon(Turnstile.fare_paid)
    def pay(self: Turnstile, lock: Lock, coin: int) -> None:
        lock.disengage()

    @locked.loop().upon(Turnstile.arm_turned)
    def block(self: Turnstile, lock: Lock) -> None:
        print("**Clunk!**  The turnstile doesn't move.")

    @unlocked.to(locked).upon(Turnstile.arm_turned)
    def turn(self: Turnstile, lock: Lock) -> None:
        lock.engage()

    return builder.build()


TurnstileImpl = buildBuilder()
turner = TurnstileImpl(Lock())
print("Paying fare 1.")
turner.fare_paid(1)
print("Walking through.")
turner.arm_turned()
print("Jumping.")
turner.arm_turned()
print("Paying fare 2.")
turner.fare_paid(1)
print("Walking through 2.")
turner.arm_turned()
print("Done.")
