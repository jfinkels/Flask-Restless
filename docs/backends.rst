.. _backends:

.. currentmodule:: flask.ext.restless

Using other database abstraction layers
=======================================

It is possible to use Flask-Restless with database abstraction layers other
than the ones based on SQLAlchemy. In order to make Flask-Restless aware of
another backend, you must first define a subclass of :class:`Backend`. When
defining the subclass, you must implement all of the methods specified in the
documentation for :class:`Backend`.

After you have defined the subclass, you must register it using
:func:`register_backend`. If your backend inference function (see
:func:`Backend.infer`) would return ``True`` for more models defined for more
than one backend, you may specify a priority for your backend inference which
defines the order in which the backend will be checked when inferring the
backend type of a model. If you do not specify a priority, the backend will be
added with the highest priority of any known backends so that it is checked
first when inferring the backend for which a model has been defined.
