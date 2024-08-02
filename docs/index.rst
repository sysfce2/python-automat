=========================================================================
Automat: Self-service finite-state machines for the programmer on the go.
=========================================================================

.. image:: https://upload.wikimedia.org/wikipedia/commons/d/db/Automat.jpg
   :width: 250
   :align: right

Automat is a library for concise, idiomatic Python expression
of finite-state automata
(particularly deterministic finite-state transducers).

.. _Garage-Example:

Why use state machines?
=======================

Sometimes you have to create an object whose behavior varies with its state,
but still wishes to present a consistent interface to its callers.

For example, let's say we are writing the software for a garage door
controller.  The garage door is composed of 4 components:

1. A motor which can be run up or down, to raise or lower the door
   respectively.
2. A sensor that activates when the door is fully open.
3. A sensor that activates when the door is fully closed.
4. A button that tells the door to open or close.

It's very important that the garage door does not get confused about its state,
because we could burn out the motor if we attempt to close an already-closed
door or open an already-open door.

With diligence and attention to detail, you can implement this correctly using
a collection of attributes on an object; is_open, is_closed,
motor_running_direction, and so on.

However, you have to keep all these attributes consistent.  As the software
becomes more complex - perhaps you want to add a safety sensor that prevents
the door from closing when someone is standing under it, for example - they all
potentially need to be updated.

Rather than adding tedious 'if' checks to every single method to make sure that
each of these flags are exactly what you expect, you can use a state machine to
ensure that if your code runs at all, it will be run with all the required
values initialized, because they have to be called in the order you declare
them.

You can read more about state machines and their advantages for Python programmers
`in an excellent article by J.P. Calderone. <http://archive.is/oWpiI>`_

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   about
   visualize
   api
   debugging
   typing
