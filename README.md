# Automat #

[![Documentation Status](https://readthedocs.org/projects/automat/badge/?version=latest)](http://automat.readthedocs.io/en/latest/)
[![Build Status](https://github.com/glyph/automat/actions/workflows/ci.yml/badge.svg?branch=trunk)](https://github.com/glyph/automat/actions/workflows/ci.yml?query=branch%3Atrunk)
[![Coverage Status](http://codecov.io/github/glyph/automat/coverage.svg?branch=trunk)](http://codecov.io/github/glyph/automat?branch=trunk)

## Self-service finite-state machines for the programmer on the go. ##

Automat is a library for concise, idiomatic Python expression of finite-state
automata (particularly deterministic finite-state transducers).

Read more here, or on [Read the Docs](https://automat.readthedocs.io/), or watch the following videos for an overview and presentation

### Why use state machines? ###

Sometimes you have to create an object whose behavior varies with its state,
but still wishes to present a consistent interface to its callers.

For example, let's say you're writing the software for a coffee machine.  It
has a lid that can be opened or closed, a chamber for water, a chamber for
coffee beans, and a button for "brew".

There are a number of possible states for the coffee machine.  It might or
might not have water.  It might or might not have beans.  The lid might be open
or closed.  The "brew" button should only actually attempt to brew coffee in
one of these configurations, and the "open lid" button should only work if the
coffee is not, in fact, brewing.

With diligence and attention to detail, you can implement this correctly using
a collection of attributes on an object; `hasWater`, `hasBeans`, `isLidOpen`
and so on.  However, you have to keep all these attributes consistent.  As the
coffee maker becomes more complex - perhaps you add an additional chamber for
flavorings so you can make hazelnut coffee, for example - you have to keep
adding more and more checks and more and more reasoning about which
combinations of states are allowed.

Rather than adding tedious `if` checks to every single method to make sure that
each of these flags are exactly what you expect, you can use a state machine to
ensure that if your code runs at all, it will be run with all the required
values initialized, because they have to be called in the order you declare
them.

You can read about state machines and their advantages for Python programmers
in more detail [in this excellent article by Jean-Paul
Calderone](https://web.archive.org/web/20160507053658/https://clusterhq.com/2013/12/05/what-is-a-state-machine/).

### What makes Automat different? ###

There are
[dozens of libraries on PyPI implementing state machines](https://pypi.org/search/?q=finite+state+machine).
So it behooves me to say why yet another one would be a good idea.

Automat is designed around this principle: while organizing your code around
state machines is a good idea, your callers don't, and shouldn't have to, care
that you've done so.  In Python, the "input" to a stateful system is a method
call; the "output" may be a method call, if you need to invoke a side effect,
or a return value, if you are just performing a computation in memory.  Most
other state-machine libraries require you to explicitly create an input object,
provide that object to a generic "input" method, and then receive results,
sometimes in terms of that library's interfaces and sometimes in terms of
classes you define yourself.

For example, a snippet of the coffee-machine example above might be implemented
as follows in naive Python:

```python
class CoffeeMachine(object):
    def brewButton(self) -> None:
        if self.hasWater and self.hasBeans and not self.isLidOpen:
            self.heatTheHeatingElement()
            # ...
```

With Automat, you'd begin with a `typing.Protocol` that describes all of your
inputs:

```python
from typing import Protocol

class CoffeeBrewer(Protocol):
    def brewButton(self) -> None:
        "The user pressed the 'brew' button."
    def putInBeans(self) -> None:
        "The user put in some beans."
```

We'll then need a concrete class to contain the shared core of state shared
among the different states:

```python
from dataclasses import dataclass

@dataclass
class BrewerCore:
    heatingElement: HeatingElement
```

Next, we need to describe our state machine, including all of our states.  For
simplicity's sake let's say that the only two states are `noBeans` and
`haveBeans`:

```python
from automat import TypeMachineBuilder

builder = TypeMachineBuilder(CoffeeBrewer, BrewerCore)
noBeans = builder.state("noBeans")
haveBeans = builder.state("haveBeans")
```

Next we can describe a simple transition; when we put in beans, we move to the
`haveBeans` state, with no other behavior.

```python
# When we don't have beans, upon putting in beans, we will then have beans
noBeans.upon(CoffeeBrewer.putInBeans).to(haveBeans).returns(None)
```

And then another transition that we describe with a decorator, one that *does*
have some behavior, that needs to heat up the heating element to brew the
coffee:

```python
@haveBeans.upon(CoffeeBrewer.brewButton).to(noBeans)
def heatUp(inputs: CoffeeBrewer, core: BrewerCore) -> None:
    """
    When we have beans, upon pressing the brew button, we will then not have
    beans any more (as they have been entered into the brewing chamber) and
    our output will be heating the heating element.
    """
    print("Brewing the coffee...")
    core.heatingElement.turnOn()
```

Then we finalize the state machine by building it, which gives us a callable
that takes a `BrewerCore` and returns a synthetic `CoffeeBrewer`

```python
newCoffeeMachine = builder.build()
```

```python
>>> coffee = newCoffeeMachine(BrewerCore(HeatingElement()))
>>> machine.putInBeans()
>>> machine.brewButton()
Brewing the coffee...
```

All of the *inputs* are provided by calling them like methods, all of the
*output behaviors* are automatically invoked when they are produced according
to the outputs specified to `upon` and all of the states are simply opaque
tokens.
