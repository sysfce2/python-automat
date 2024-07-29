from dataclasses import dataclass
from typing import Protocol

from automat import TypeMachineBuilder, TypifiedState


@dataclass
class Beans:
    description: str


@dataclass
class BeanHolder:
    beans: Beans


class Brewer(Protocol):
    def brew_button(self) -> None:
        "The user pressed the 'brew' button."

    def put_in_beans(self, beans: Beans) -> None:
        "The user put in some beans."


class BrewCore:
    "state for the brew process"



def _coffee_machine() -> TypeMachineBuilder[Brewer, BrewCore]:
    """
    Best practice: these functions are all fed in to the builder, they don't
    need to call each other, so they don't need to be defined globally.  Use a
    function scope to avoid littering a module with states and such.
    """
    builder = TypeMachineBuilder[Brewer, BrewCore](BrewCore)

    def make_bean_state(
        # these two are part of the signature
        brewer: Brewer,
        core: BrewCore,
        # this is the signature of put_in_beans *and any other method that wants to
        # transition to have_beans*
        beans: Beans,
    ) -> BeanHolder:
        "this should be able to be a lambda in common practice but it is expanded for pedagogical purposes here"
        return BeanHolder(beans)


    have_beans: TypifiedState[Beans] = builder.stateful_state(
        "HaveBeans", state_specific_data=make_bean_state
    )
    dont_have_beans = builder.state("DontHaveBeans")


    @have_beans.stateful_transition(Brewer.brew_button, dont_have_beans)
    def brew(brewer: Brewer, core: BrewCore, holder: BeanHolder) -> None:
        print(f"yum, {holder.beans.description} beans")

    @dont_have_beans.transition(Brewer.brew_button, have_beans)
    def put(brewer: Brewer, core: BrewCore, beans: Beans) -> None:
        print("beans inserted")
    return builder

CoffeeMachine = _coffee_machine().build()

