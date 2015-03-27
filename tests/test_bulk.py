"""
    tests.test_bulk
    ~~~~~~~~~~~~~~~

    Unit tests for the `JSON API Bulk extension`_.

    .. _JSON API Bulk extension: http://jsonapi.org/extensions/bulk

    :copyright: 2015 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com> and
                contributors.
    :license: GNU AGPLv3+ or BSD

"""
from sqlalchemy import Column
from sqlalchemy import Integer

from .helpers import ManagerTestBase


class TestCreating(ManagerTestBase):
    """Tests for creating multiple resources.

    For more information, see the `Creating Multiple Resources`_ section of the
    JSON API Bulk extension specification.

    .. _Creating Multiple Resources: http://jsonapi.org/extensions/bulk/#creating-multiple-resources

    """

    def setUp(self):
        super(TestCreating, self).setUp()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)

        self.Person = Person
        self.Base.metadata.create_all()
        self.manager.create_api(Person, methods=['POST'], enable_bulk=True)

    def test_create(self):
        """Tests for creating multiple resources."""
        assert False, 'Not implemented'


class TestUpdating(ManagerTestBase):
    """Tests for updating multiple resources.

    For more information, see the `Updating Multiple Resources`_ section of the
    JSON API Bulk extension specification.

    .. _Updating Multiple Resources: http://jsonapi.org/extensions/bulk/#updating-multiple-resources

    """

    def setUp(self):
        super(TestUpdating, self).setUp()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)

        self.Person = Person
        self.Base.metadata.create_all()
        self.manager.create_api(Person, methods=['PUT'], enable_bulk=True)

    def test_update(self):
        """Tests for updating multiple resources."""
        assert False, 'Not implemented'


class TestDeleting(ManagerTestBase):
    """Tests for deleting multiple resources.

    For more information, see the `Deleting Multiple Resources`_ section of the
    JSON API Bulk extension specification.

    .. _Deleting Multiple Resources: http://jsonapi.org/extensions/bulk/#deleting-multiple-resources

    """

    def setUp(self):
        super(TestDeleting, self).setUp()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)

        self.Person = Person
        self.Base.metadata.create_all()
        self.manager.create_api(Person, methods=['DELETE'], enable_bulk=True)

    def test_delete(self):
        """Tests for deleting multiple resources."""
        assert False, 'Not implemented'
