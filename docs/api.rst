API
===

.. module:: flask_restless

This part of the documentation documents all the public classes and functions
in Flask-Restless.

The API Manager class
---------------------

.. autoclass:: APIManager

   .. automethod:: init_app

   .. automethod:: create_api

   .. automethod:: create_api_blueprint

Global helper functions
-----------------------

.. autofunction:: collection_name(model, _apimanager=None)

.. autofunction:: model_for(collection_name, _apimanager=None)

.. autofunction:: serializer_for(model, _apimanager=None)

.. autofunction:: primary_key_for(model, _apimanager=None)

.. autofunction:: url_for(model, instid=None, relationname=None, relationinstid=None, _apimanager=None, **kw)

Serialization and deserialization
---------------------------------

.. autoclass:: DefaultSerializer

.. autoclass:: DefaultDeserializer

.. autoclass:: SerializationException

.. autoclass:: DeserializationException

.. autoclass:: MultipleExceptions


Pre- and postprocessor helpers
------------------------------

.. autoclass:: ProcessingException
