.. _requestformat:

.. currentmodule:: flask.ext.restless

Format of requests and responses
================================

Requests and responses are all in JSON format, so the mimetype is
:mimetype:`application/json`. Ensure that requests you make have the correct
mimetype and/or content type.

Suppose we have the following models::

    from flask import Flask
    from flask.ext.sqlalchemy import SQLAlchemy

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
    db = SQLAlchemy(app)

    class Person(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.Unicode, unique=True)
        birth_date = db.Column(db.Date)
        computers = db.relationship('Computer',
                                    backref=db.backref('owner',
                                                       lazy='dynamic'))

    class Computer(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.Unicode, unique=True)
        vendor = db.Column(db.Unicode)
        owner_id = db.Column(db.Integer, db.ForeignKey('person.id'))
        purchase_time = db.Column(db.DateTime)


Also suppose we have registered an API for these models at ``/api/person`` and
``/api/computer``, respectively.

.. note::

   For all requests that would return a list of results, the top-level JSON
   object is a mapping from ``"objects"`` to the list. JSON lists are not sent
   as top-level objects for security reasons. For more information, see `this
   <http://flask.pocoo.org/docs/security/#json-security>`_.

.. http:get:: /api/person

   Gets a list of all ``Person`` objects.

   **Sample response**:

   .. sourcecode:: http

       HTTP/1.1 200 OK

       {"objects": [{"id": 1, "name": "Jeffrey", "age": 24}, ...]}

.. http:get:: /api/person?q=<searchjson>

   Gets a list of all ``Person`` objects which meet the criteria of the
   specified search. For more information on the format of the value of the
   ``q`` parameter, see :ref:`searchformat`.

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK

      {"objects": [{"id": 1, "name": "Jeffrey", "age": 24}, ...]}

   If the value of the ``q`` parameter indicates that a function should be
   evaluated on the matched instances instead, the response would look like
   this:

   .. sourcecode:: http

      HTTP/1.1 200 OK

      {"sum__age": 135, "avg__age": 25.5, ...}

.. http:get:: /api/person/(int:id)

   Gets a single instance of ``Person`` with the specified ID.

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK

      {"id": 1, "name": "Jeffrey", "age": 24}

.. http:delete:: /api/person/(int:id)

   Deletes the instance of ``Person`` with the specified ID.

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Content

.. http:post:: /api/person

   Creates a new person with initial attributes specified as a JSON string in
   the body of the request.

   **Sample request**:

   .. sourcecode:: http

      POST /api/person HTTP/1.1
      Host: example.com

      {"name": "Jeffrey", "age": 24}

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created

      {"id": 1}

.. http:patch:: /api/person?q=<searchjson>
.. http:put:: /api/person/?q=<searchjson>

   Sets specified attributes on every instance of ``Person`` which meets the
   search criteria described in the ``q`` query parameter.
   :http:put:`/api/person` is an alias for :http:patch:`/api/person`, because
   the latter is more semantically correct but the former is part of the core
   HTTP standard. For more information on the format of the value of the ``q``
   parameter, see :ref:`searchformat`.

   The response will return a JSON object which specifies the number of
   instances in the ``Person`` database which were modified.

   **Sample request**:

   Suppose the database contains exactly three people with the letter "y" in
   their names. Suppose that the client makes a request that has query
   parameter ``q`` set to the following JSON object (as a string):

   .. sourcecode:: javascript

      { "filters": [{"name": "name", "op": "like", "val": "%y%"}] }

   and with the content of the request:

   .. sourcecode:: http

      PATCH /api/person/1 HTTP/1.1
      Host: example.com

      {"age": 1}

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created

      {"num_modified": 3}

.. http:patch:: /api/person/(int:id)
.. http:put:: /api/person/(int:id)

   Sets specified attributes on the instance of ``Person`` with the specified
   ID number. :http:put:`/api/person/1` is an alias for
   :http:patch:`/api/person/1`, because the latter is more semantically correct
   but the former is part of the core HTTP standard.

   **Sample request**:

   .. sourcecode:: http

      PATCH /api/person/1 HTTP/1.1
      Host: example.com

      {"name": "Foobar"}

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created

      {"id": 1, "name": "Foobar", "age": 24}

   To add an existing object to a one-to-many relationship, a request must take
   the following form.

   **Sample request**:

   .. sourcecode:: http

      PATCH /api/person/1 HTTP/1.1
      Host: example.com

      { "computers":
        {
          "add": [ {"id": 1} ]
        }
      }

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK

      {
        "id": 1,
        "name": "Jeffrey",
        "age": 24,
        "computers": [ {"id": 1, "manufacturer": "Dell", "model": "Inspiron"} ]
      }

   To add a new object to a one-to-many relationship, a request must take the
   following form.

   **Sample request**:

   .. sourcecode:: http

      PATCH /api/person/1 HTTP/1.1
      Host: example.com

      { "computers":
        {
          "add": [ {"id": 1} ]
        }
      }

   .. warning::

      The response does not denote that a new instance has been created for the
      ``Computer`` model.

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK

      {
        "id": 1,
        "name": "Jeffrey",
        "age": 24,
        "computers": [ {"id": 1, "manufacturer": "Dell", "model": "Inspiron"} ]
      }

   To remove an existing object (without deleting that object from its own
   database) from a one-to-many relationship, a request must take the following
   form.

   **Sample request**:

   .. sourcecode:: http

      PATCH /api/person/1 HTTP/1.1
      Host: example.com

      { "computers":
        {
          "remove": [ {"id": 2} ]
        }
      }

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK

      {
        "id": 1,
        "name": "Jeffrey",
        "age": 24,
        "computers": [
          {"id": 1, "manufacturer": "Dell", "model": "Inspiron 9300"},
          {"id": 3, "manufacturer": "Apple", "model": "MacBook"}
        ]
      }

   To remove an existing object from a one-to-many relationship and
   additionally delete it from its own database, a request must take the
   following form.

   **Sample request**:

   .. sourcecode:: http

      PATCH /api/person/1 HTTP/1.1
      Host: example.com

      { "computers":
        {
          "remove": [ {"id": 2, "__delete__": true} ]
        }
      }

   .. warning::

      The response does not denote that the instance was deleted from its own
      database.

   **Sample response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK

      {
        "id": 1,
        "name": "Jeffrey",
        "age": 24,
        "computers": [
          {"id": 1, "manufacturer": "Dell", "model": "Inspiron 9300"},
          {"id": 3, "manufacturer": "Apple", "model": "MacBook"}
        ]
      }

Error messages
--------------

Most errors return :http:statuscode:`400`. A bad request, for example, will
receive a response like this:

.. sourcecode:: http

   HTTP/1.1 400 Bad Request

   {"message": "Unable to decode data"}

.. _functionevaluation:

Function evaluation
-------------------

If the ``allow_functions`` keyword argument is set to ``True`` when creating an
API for a model using :meth:`APIManager.create_api`, then an endpoint will be
made available for :http:get:`/api/eval/person` which responds to requests for
evaluation of functions on all instances the model.

**Sample request**:

.. sourcecode:: http

   GET /api/eval/person HTTP/1.1

   { "functions":
     [
       {"name": "sum", "field": "age"},
       {"name": "avg", "field": "height"}
     ]
   }

The format of the response is

.. sourcecode:: http

   HTTP/1.1 200 OK

   {"sum__age": 100, "avg_height": 68}

If no functions are specified in the request, the response will contain
the empty JSON object, ``{}``.

.. note::

   The functions whose names are given in the request will be evaluated using
   SQLAlchemy's `func
   <http://docs.sqlalchemy.org/en/latest/core/expression_api.html#sqlalchemy.sql.expression.func>`_
   object.
