from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from automat import TypifiedBuilder

@dataclass
class Beans:
    description: str


@dataclass
class Water:
    "It's Water"


@dataclass
class Carafe:
    "It's a carafe"
    full: bool = False


@dataclass
class Ready:
    beans: Beans
    water: Water
    carafe: Carafe

    def brew(self) -> Mixture:
        print(f"brewing {self.beans} with {self.water} in {self.carafe}")
        return Mixture(self.beans, self.water)


@dataclass
class Mixture:
    beans: Beans
    water: Water


class Brewer(Protocol):
    def brew_button(self) -> None:
        "The user pressed the 'brew' button."

    def wait_a_while(self) -> Mixture:
        "Allow some time to pass."

    def put_in_beans(self, beans: Beans) -> None:
        "The user put in some beans."

    def put_in_water(self, water: Water) -> None:
        "The user put in some water."

    def put_in_carafe(self, carafe: Carafe) -> None:
        "The user put the mug"


class _BrewerInternals(Brewer, Protocol):
    def _ready(self, beans: Beans, water: Water, carafe: Carafe) -> None:
        "We are ready with all of our inputs."


@dataclass
class Light:
    on: bool = False


@dataclass
class BrewCore:
    "state for the brew process"
    ready_light: Light
    brew_light: Light
    beans: Beans | None = None
    water: Water | None = None
    carafe: Carafe | None = None
    brewing: Mixture | None = None


def _coffee_machine() -> TypifiedBuilder[_BrewerInternals, BrewCore]:
    """
    Best practice: these functions are all fed in to the builder, they don't
    need to call each other, so they don't need to be defined globally.  Use a
    function scope to avoid littering a module with states and such.
    """
    builder = TypifiedBuilder(_BrewerInternals, BrewCore)
    # reveal_type(builder)
    not_ready = builder.state("HaveBeans")

    def build_ready(
        brewer: _BrewerInternals,
        core: BrewCore,
        beans: Beans,
        water: Water,
        carafe: Carafe,
    ) -> Ready:
        return Ready(beans, water, carafe)

    def build_mixture(
        brewer: _BrewerInternals,
        core: BrewCore,
    ) -> Mixture:
        raise NotImplementedError(
            "mixture must be conveyed by return value, we can't build it"
        )

    ready = builder.stateful_state("Ready", Ready, build_ready)
    brewing = builder.stateful_state("Brewing", Mixture, build_mixture)

    def ready_check(brewer: _BrewerInternals, core: BrewCore) -> None:
        if (
            core.beans is not None
            and core.water is not None
            and core.carafe is not None
            and core.carafe.full is not None
        ):
            brewer._ready(core.beans, core.water, core.carafe)

    @not_ready.transition(Brewer.put_in_beans, not_ready)
    def put_beans(brewer: _BrewerInternals, core: BrewCore, beans: Beans) -> None:
        core.beans = beans
        ready_check(brewer, core)

    @not_ready.transition(Brewer.put_in_water, not_ready)
    def put_water(brewer: _BrewerInternals, core: BrewCore, water: Water) -> None:
        core.water = water
        ready_check(brewer, core)

    @not_ready.transition(Brewer.put_in_carafe, not_ready)
    def put_carafe(brewer: _BrewerInternals, core: BrewCore, carafe: Carafe) -> None:
        core.carafe = carafe
        ready_check(brewer, core)

    @not_ready.transition(_BrewerInternals._ready, ready)
    def get_ready(
        brewer: _BrewerInternals,
        core: BrewCore,
        beans: Beans,
        water: Water,
        carafe: Carafe,
    ) -> None:
        ...

    # all transitions into this state should invoke this at some point in the
    # transition; after or before the main function?
    @ready.stateful_setup()
    def ready_now(brewer: _BrewerInternals, core: BrewCore, ready: Ready) -> None:
        core.ready_light.on = True

    # all transitions out should invoke this
    @ready.stateful_cleanup()
    def not_ready_anymore(
        brewer: _BrewerInternals, core: BrewCore, ready: Ready
    ) -> None:
        core.ready_light.on = False

    @ready.stateful_convey(Brewer.brew_button, brewing)
    def brew(
        brewer: _BrewerInternals, core: BrewCore, ready: Ready
    ) -> tuple[
        # it's a tuple because we have to convey the result of
        # brew_button(None) as well as the required state for the 'brewing'
        # stateful state(Mixture)
        None,
        Mixture,
    ]:
        core.brew_light.on = True
        return (None, ready.brew())

    @brewing.stateful_transition(_BrewerInternals.wait_a_while, not_ready)
    def brewed(brewer: _BrewerInternals, core: BrewCore, mixture: Mixture) -> Mixture:
        core.brew_light.on = False
        return mixture

    return builder


CoffeeMachine: Callable[[BrewCore], Brewer] = _coffee_machine().build()

if __name__ == "__main__":
    machine = CoffeeMachine(core := BrewCore(Light(), Light()))
    machine.put_in_beans(Beans("light roast"))
    machine.put_in_water(Water())
    machine.put_in_carafe(Carafe())
    machine.brew_button()
    brewed = machine.wait_a_while()
    print(brewed)
