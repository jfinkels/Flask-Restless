# serializers.py - custom serializers for unit tests
# using the marshmallow de/serialization library
#
# .._Marshmallow: http://marshmallow.readthedocs.io/en/latest/index.html
#
# Copyright 2018 Kiptoo Magutt <kiptoo.this@gmail.com>.
# Copyright 2012, 2013, 2014, 2015, 2016 Jeffrey Finkelstein
#           <jeffrey.finkelstein@gmail.com> and contributors.
#
# This file is part of Flask-Restless.
#
# Flask-Restless is distributed under both the GNU Affero General Public
# License version 3 and under the 3-clause BSD license. For more
# information, see LICENSE.AGPL and LICENSE.BSD.
"""Helper functions for unit tests."""

from flask_restless import DefaultSerializer
from flask_restless import DefaultDeserializer


class MarshmallowSerializer(DefaultSerializer):
    """
    Base class for models that need custom serializers
    using the marshmallow library

    See
        :class:`TestUpdating.TestSupport.AddressSchema`
        for example usage

    """
    schema_class = None

    def serialize(self, instance, only=None):
        schema = self.schema_class(only=only)
        return schema.dump(instance).data

    def serialize_many(self, instances, only=None):
        schema = self.schema_class(many=True, only=only)
        return schema.dump(instances).data


class MarshmallowDeserializer(DefaultDeserializer):

    schema_class = None

    def deserialize(self, document):
        schema = self.schema_class()
        return schema.load(document).data

    def deserialize_many(self, document):
        schema = self.schema_class(many=True)
        return schema.load(document).data
