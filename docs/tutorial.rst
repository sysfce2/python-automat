Tutorial: Building a Garage Door Controller
===========================================

Let's consider :ref:`the garage door example from the
introduction<Garage-Example>`.

Automat takes great care to present a state machine as a collection of regular
methods.  So we define what those methods *are* with a
:py:class:`typing.Protocol` that describes them.

.. literalinclude:: examples/garage_door.py
   :pyobject: GarageController

This protocol tells us that only 3 things can happen to our controller from the
outside world (its inputs): the user can push the button, the "door is all the
way up" sensor can emit a signal, or the "door is all the way down" sensor can
emit a signal.  So those are our inputs.

However, our state machine also needs to be able to *affect* things in the
world (its outputs). As we are writing a program in Python, these come in the
form of a Python object that can be shared between all the states that
implement our controller, and for this purpose we define a simple shared-data
class:

.. literalinclude:: examples/garage_door.py
   :pyobject: DoorDevices

Here we have a reference to a ``Motor`` that can open and close the door, and
an ``Alarm`` that can beep to alert people that the door is closing.

Next we need to combine those together, using a
:py:class:`automat.TypeMachineBuilder`.

.. literalinclude:: examples/garage_door.py
   :start-after: start building
   :end-before: build states

Next we have to define our states.  Let's start with four simple ones:

1. closed - the door is closed and idle
2. opening - the door is actively opening
3. opened - the door is open and idle
4. closing - the door is actively closing

.. literalinclude:: examples/garage_door.py
   :start-after: build states
   :end-before: end states

To describe the state machine, we define a series of transitions, using the
method ``.upon()``:

.. literalinclude:: examples/garage_door.py
   :start-after: build methods
   :end-before: end methods



Building and using the state machine
------------------------------------

Now that we have described all the inputs, states, and output behaviors, it's
time to actually build the state machine:

.. literalinclude:: examples/garage_door.py
   :start-after: do build
   :end-before: end building

The :py:meth:`automat.TypeMachineBuilder.build` method creates a callable that
takes an instance of its state core (``DoorDevices``) and returns an object
that conforms to its inputs protocol (``GarageController``).  We can then take
this ``machineFactory`` and call it, like so:

.. literalinclude:: examples/garage_door.py
   :start-after: do instantiate
   :end-before: end instantiate

Because we defined ``closed`` as our first state above, the machine begins in
that state by default.  So the first thing we'll do is to open the door:

.. literalinclude:: examples/garage_door.py
   :start-after: do open
   :end-before: end open

If we run this, we will then see some output, indicating that the motor is
running:

.. code-block::

   motor running up

If we press the button again, rather than silently double-starting the motor,
we will get an error, since we haven't yet defined a state transition for this
state yet.  The traceback looks like this:

.. code-block::

    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
        machine.pushButton()
      File ".../automat/_typed.py", line 419, in implementation
        [outputs, tracer] = transitioner.transition(methodInput)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../automat/_core.py", line 196, in transition
        outState, outputSymbols = self._automaton.outputForInput(
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../automat/_core.py", line 169, in outputForInput
        raise NoTransition(state=inState, symbol=inputSymbol)
    automat._core.NoTransition: no transition for pushButton in TypedState(name='opening')

At first, this might seem like it's making more work for you.  If you don't
want to crash the code that calls your methods, you need to provide many more
implementations of the same method for each different state.  But, in this
case, by causing this exception *before* running any of your code, Automat is
protecting your internal state: although client code will get an exception, the
*internal* state of your garage door controller will remain consistent.

If you did not explicitly take a specific state into consideration while
implementing some behavior, that behavior will never be invoked.  Therefore, it
cannot do something potentially harmful like double-starting the motor.

If we trigger the open sensor so that the door completes its transition to the
'open' state, then push the button again, the buzzer will sound and the door
will descend:

.. literalinclude:: examples/garage_door.py
   :start-after: sensor and close
   :end-before: end close


.. code-block::

   motor stopped
   beep beep beep
   motor running down

Input for Inputs and Output for Outputs
=======================================

Quite often you want to be able to pass parameters to your methods,
as well as inspecting their results.
For example, when you brew the coffee,
you might expect a cup of coffee to result,
and you would like to see what kind of coffee it is.
And if you were to put delicious hand-roasted small-batch artisanal
beans into the machine, you would expect a *better* cup of coffee
than if you were to use mass-produced beans.
You would do this in plain old Python by adding a parameter,
so that's how you do it in Automat as well.


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.input()
        def put_in_beans(self, beans):
            "The user put in some beans."


However, one important difference here is that
*we can't add any implementation code to the input method*.
Inputs are purely a declaration of the interface;
the behavior must all come from outputs.
Therefore, the change in the state of the coffee machine
must be represented as an output.
We can add an output method like this:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.output()
        def _save_beans(self, beans):
            "The beans are now in the machine; save them."
            self._beans = beans


and then connect it to the `put_in_beans` by changing the transition from
`dont_have_beans` to `have_beans` like so:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        dont_have_beans.upon(put_in_beans, enter=have_beans,
                             outputs=[_save_beans])


Now, when you call:


.. code-block:: python

    coffee_machine.put_in_beans("real good beans")


the machine will remember the beans for later.

So how do we get the beans back out again?
One of our outputs needs to have a return value.
It would make sense if our `brew_button` method
returned the cup of coffee that it made, so we should add an output.
So, in addition to heating the heating element,
let's add a return value that describes the coffee.
First a new output:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.output()
        def _describe_coffee(self):
            return "A cup of coffee made with {}.".format(self._beans)


Note that we don't need to check first whether `self._beans` exists or not,
because we can only reach this output method if the state machine says we've
gone through a set of states that sets this attribute.

Now, we need to hook up `_describe_coffee` to the process of brewing,
so change the brewing transition to:


.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        have_beans.upon(brew_button, enter=dont_have_beans,
                        outputs=[_heat_the_heating_element,
                                 _describe_coffee])


Now, we can call it:


>>> coffee_machine.brew_button()
[None, 'A cup of coffee made with real good beans.']


Except... wait a second, what's that `None` doing there?

Since every input can produce multiple outputs, in automat, the default return
value from every input invocation is a `list`.  In this case, we have both
`_heat_the_heating_element` and `_describe_coffee` outputs, so we're seeing
both of their return values.  However, this can be customized, with the
`collector` argument to :py:meth:`MethodicalMachine.upon`; the `collector` is a
callable which takes an iterable of all the outputs' return values and
"collects" a single return value to return to the caller of the state machine.

In this case, we only care about the last output,
so we can adjust the call to :py:meth:`MethodicalMachine.upon` like this:

.. code-block:: python

    class CoffeeBrewer(object):
        _machine = MethodicalMachine()

        # ...

        have_beans.upon(brew_button, enter=dont_have_beans,
                        outputs=[_heat_the_heating_element,
                                 _describe_coffee],
                        collector=lambda iterable: list(iterable)[-1]
        )


And now, we'll get just the return value we want:


>>> coffee_machine.brew_button()
'A cup of coffee made with real good beans.'


State-specific Data
-------------------

TKTKTK

- possible garage-door example? "stuck" state for when button is pressed when
  door is opening or closing. same behavior in either case (pause, close if
  button not pressed after timeout) but the direction to go in and the delayed
  call to cancel could both be stored in a Stuck SSD.  It's a bit of a reach?

OR

- "automat" (vending machine) example: counting up coins to buy an item;
  state-specific data created when first coin inserted, balance tracked on SSD
  object, change + food dispensed and return to idle state.

Reentrancy Limitations
----------------------

TKTKTK

this one might need to be a little fake as you tend to hit these with complex
asynchronous/semi-synchronous APIs in real life


How do I get the current state of a state machine?
==================================================

Don't do that.

One major reason for having a state machine is that you want the callers of the
state machine to just provide the appropriate input to the machine at the
appropriate time, and *not have to check themselves* what state the machine is
in.  So if you are tempted to write some code like this:


.. code-block:: python

    if connection_state_machine.state == "CONNECTED":
        connection_state_machine.send_message()
    else:
        print("not connected")


Instead, just make your calling code do this:

.. code-block:: python

    connection_state_machine.send_message()

and then change your state machine to look like this:


.. code-block:: python

    class Connector(Protocol):
        def send_message(self) -> None:
            "send a message"
    class Core:
        _transport: Transport

    builder = TypeMachine(Connector, Core)
    connected = builder.state("connector")
    not_connected = builder.state("not_connected")
    @connected.upon(Connector.send_message).loop()
    def _actually_send_message(connector: Connector, core: Core) -> None:
        core._transport.send(b"message")
    @not_connected.upon(Connector.send_message).loop()
    def _report_sending_failure(connector: Connector, core: Core):
        print("not connected")
    machine = builder.build()


so that the responsibility for knowing which state the state machine is in
remains within the state machine itself.


If I can't get the state of the state machine, how can I save it to (a database, an API response, a file on disk...)
====================================================================================================================

TKTKTK

- no need for ``serialized=`` because we can use the ``str`` values passed to
  :py:meth:`TypeMachineBuilder.state`, those have to be serializable

- we can just implement serialization as a regular input, the only thing that
  we are missing is the ability to jump to a specific state using the built
  constructor.  so that constructor can optionally take a state argument, and
  be ``@overload``-ed such that a ``TypedState`` requires a parameter of
  the ``Data`` typevar type, whereas ``TypedDataState`` does not.  Then we can
  just instantiate the transitioner with the appropriate state variable.


legacy version follows:

There are APIs for serializing the state machine.

First, you have to decide on a persistent representation of each state,
via the `serialized=` argument to the `MethodicalMachine.state()` decorator.

Let's take this very simple "light switch" state machine,
which can be on or off, and flipped to reverse its state:


.. code-block:: python

    class LightSwitch(object):
        _machine = MethodicalMachine()

        @_machine.state(serialized="on")
        def on_state(self):
            "the switch is on"

        @_machine.state(serialized="off", initial=True)
        def off_state(self):
            "the switch is off"

        @_machine.input()
        def flip(self):
            "flip the switch"

        on_state.upon(flip, enter=off_state, outputs=[])
        off_state.upon(flip, enter=on_state, outputs=[])


In this case, we've chosen a serialized representation for each state
via the `serialized` argument.
The on state is represented by the string `"on"`,
and the off state is represented by the string `"off"`.

Now, let's just add an input that lets us tell if the switch is on or not.


.. code-block:: python

    from operator import itemgetter

    first = itemgetter(0)

    class LightSwitch(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.input()
        def query_power(self):
            "return True if powered, False otherwise"

        @_machine.output()
        def _is_powered(self):
            return True

        @_machine.output()
        def _not_powered(self):
            return False

        on_state.upon(
            query_power, enter=on_state, outputs=[_is_powered], collector=first
        )
        off_state.upon(
            query_power, enter=off_state, outputs=[_not_powered], collector=first
        )


To save the state, we have the `MethodicalMachine.serializer()` method.
A method decorated with `@serializer()` gets an extra argument injected
at the beginning of its argument list: the serialized identifier for the state.
In this case, either `"on"` or `"off"`.
Since state machine output methods can also affect other state on the object,
a serializer method is expected to return *all* relevant state for serialization.

For our simple light switch, such a method might look like this:

.. code-block:: python

    class LightSwitch(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.serializer()
        def save(self, state):
            return {"is-it-on": state}


Serializers can be public methods, and they can return whatever you like.
If necessary, you can have different serializers -
just multiple methods decorated with `@_machine.serializer()` -
for different formats;
return one data-structure for JSON, one for XML, one for a database row, and so on.

When it comes time to unserialize, though, you generally want a private method,
because an unserializer has to take a not-fully-initialized instance
and populate it with state.
It is expected to *return* the serialized machine state token
that was passed to the serializer, but it can take whatever arguments you like.
Of course, in order to return that,
it probably has to take it somewhere in its arguments,
so it will generally take whatever a paired serializer has returned as an argument.

So our unserializer would look like this:


.. code-block:: python

    class LightSwitch(object):
        _machine = MethodicalMachine()

        # ...

        @_machine.unserializer()
        def _restore(self, blob):
            return blob["is-it-on"]


Generally you will want a classmethod deserialization constructor
which you write yourself to call this,
so that you know how to create an instance of your own object, like so:


.. code-block:: python

    class LightSwitch(object):
        _machine = MethodicalMachine()

        # ...

        @classmethod
        def from_blob(cls, blob):
            self = cls()
            self._restore(blob)
            return self


Saving and loading our `LightSwitch`
along with its state-machine state can now be accomplished as follows:


>>> switch1 = LightSwitch()
>>> switch1.query_power()
False
>>> switch1.flip()
[]
>>> switch1.query_power()
True
>>> blob = switch1.save()
>>> switch2 = LightSwitch.from_blob(blob)
>>> switch2.query_power()
True


More comprehensive (tested, working) examples are present in `docs/examples`.

Go forth and machine all the state!
