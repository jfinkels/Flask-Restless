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

#     def test_post_multiple(self):
#         data = dict(person=[dict(name='foo', age=10), dict(name='bar')])
#         response = self.app.post('/api/person', data=dumps(data))
#         assert response.status_code == 201
#         people = loads(response.data)['person']
#         assert sorted(['foo', 'bar']) == sorted(p['name'] for p in people)
#         # The server must respond with a Location header for each person.
#         #
#         # Sort the locations by primary key, which is the last character in the
#         # Location URL.
#         locations = sorted(response.headers.getlist('Location'),
#                            key=lambda s: s[-1])
#         assert locations[0].endswith('/api/person/1')
#         assert locations[1].endswith('/api/person/2')



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

    # TODO this is not required by the JSON API spec, but may be usable.
    #
    # def test_disallow_patch_many(self):
    #     """Tests that disallowing "patch many" requests responds with a
    #     :http:statuscode:`405`.

    #     """
    #     response = self.app.patch('/api/person', data=dumps(dict(name='foo')))
    #     assert response.status_code == 405

    # TODO this is not required by the JSON API spec.
    #
    # def test_patch_many(self):
    #     """Test for updating a collection of instances of the model using the
    #     :http:method:`patch` method.

    #     """
    #     # recreate the api to allow patch many at /api/v2/person
    #     self.manager.create_api(self.Person, methods=['GET', 'POST', 'PATCH'],
    #                             allow_patch_many=True, url_prefix='/api/v2')

    #     # Creating some people
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Lincoln', 'age': 23}))
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Lucy', 'age': 23}))
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Mary', 'age': 25}))

    #     # Trying to pass invalid data to the update method
    #     resp = self.app.patch('/api/v2/person', data='Hello there')
    #     assert resp.status_code == 400
    #     assert loads(resp.data)['message'] == 'Unable to decode data'

    #     # Changing the birth date field of the entire collection
    #     day, month, year = 15, 9, 1986
    #     birth_date = date(year, month, day).strftime('%d/%m/%Y')  # iso8601
    #     form = {'birth_date': birth_date}
    #     self.app.patch('/api/v2/person', data=dumps(form))

    #     # Finally, testing if the change was made
    #     response = self.app.get('/api/v2/person')
    #     loaded = loads(response.data)['objects']
    #     for i in loaded:
    #         expected = '{0:4d}-{1:02d}-{2:02d}'.format(year, month, day)
    #         assert i['birth_date'] == expected

    # TODO this is not required by the JSON API spec.
    #
    # def test_patch_many_with_filter(self):
    #     """Test for updating a collection of instances of the model using a
    #     :http:method:patch request with filters.

    #     """
    #     # recreate the api to allow patch many at /api/v2/person
    #     self.manager.create_api(self.Person, methods=['GET', 'POST', 'PATCH'],
    #                             allow_patch_many=True, url_prefix='/api/v2')
    #     # Creating some people
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Lincoln', 'age': 23}))
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Lucy', 'age': 23}))
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Mary', 'age': 25}))
    #     search = {'filters': [{'name': 'name', 'val': u'Lincoln',
    #                            'op': 'equals'}]}
    #     # Changing the birth date field for objects where name field equals
    #     # Lincoln
    #     day, month, year = 15, 9, 1986
    #     birth_date = date(year, month, day).strftime('%d/%m/%Y')  # iso8601
    #     form = {'birth_date': birth_date, 'q': search}
    #     response = self.app.patch('/api/v2/person', data=dumps(form))
    #     num_modified = loads(response.data)['num_modified']
    #     assert num_modified == 1

    # def test_preprocessor(self):
    #     """Tests :http:method:`put` requests for a collection of resources with
    #     a preprocessor function.

    #     """
    #     person1 = self.Person(id=1, name='foo')
    #     person2 = self.Person(id=2, name='bar')
    #     self.session.add_all([person1, person2])
    #     self.session.commit()

    #     def set_name(data=None, **kw):
    #         """Sets the name attribute of the incoming data object, regardless
    #         of the value requested by the client.

    #         """
    #         if data is not None:
    #             data['data']['name'] = 'xyzzy'

    #     preprocessors = dict(PUT_COLLECTION=[set_name])
    #     self.manager.create_api(self.Person, methods=['PUT'],
    #                             allow_patch_many=True,
    #                             preprocessors=preprocessors)
    #     data = dict(data=dict(type='person', name='baz'))
    #     response = self.app.put('/api/person', data=dumps(data))
    #     assert response.status_code == 200
    #     document = loads(response.data)
    #     assert document['meta']['total'] == 2
    #     assert all(person.name == 'xyzzy' for person in (person1, person2))

#     def test_put_multiple(self):
#         person1 = self.Person(id=1, name='foo')
#         person2 = self.Person(id=2, age=99)
#         self.session.add_all([person1, person2])
#         self.session.commit()

#         # Updates a different field on each person.
#         data = dict(person=[dict(id=1, name='bar'), dict(id=2, age=10)])
#         response = self.app.put('/api/person/1,2', data=dumps(data))
#         assert response.status_code == 204
#         assert person1.name == 'bar'
#         assert person2.age == 10

#     def test_put_multiple_without_id(self):
#         person1 = self.Person(id=1, name='foo')
#         person2 = self.Person(id=2, age=99)
#         self.session.add_all([person1, person2])
#         self.session.commit()

#         # In order to avoid ambiguity, attempts to update multiple instances
#         # without specifying the ID in each object results in an error.
#         data = dict(person=[dict(name='bar'), dict(id=2, age=10)])
#         response = self.app.put('/api/person/1,2', data=dumps(data))
#         assert response.status_code == 400
#         # TODO Check the error message, description, etc.


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

    @skip('Deleting a collection only appears in the JSON API bulk extension')
    def test_collection(self):
        """Tests for deleting all instances of a collection."""
        self.session.add_all(self.Person() for n in range(3))
        self.session.commit()
        self.manager.create_api(self.Person, methods=['DELETE'],
                                allow_delete_many=True, url_prefix='/api2')
        response = self.app.delete('/api2/person')
        assert response.status_code == 200
        document = loads(response.data)
        assert document['meta']['total'] == 3
        assert self.session.query(self.Person).count() == 0

    @skip('Deleting a collection only appears in the JSON API bulk extension')
    def test_empty_collection(self):
        """Tests that deleting an empty collection still yields a
        :http:status:`200` response.

        """
        self.manager.create_api(self.Person, methods=['DELETE'],
                                allow_delete_many=True, url_prefix='/api2')
        response = self.app.delete('/api2/person')
        assert response.status_code == 200
        document = loads(response.data)
        assert document['meta']['total'] == 0

    @skip('Deleting a collection only appears in the JSON API bulk extension')
    def test_filtered_collection(self):
        """Tests for deleting instances of a collection selected by filters."""
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        person3 = self.Person(id=3)
        self.session.add_all([person1, person2, person3])
        self.session.commit()
        self.manager.create_api(self.Person, methods=['DELETE'],
                                allow_delete_many=True, url_prefix='/api2')
        filters = [dict(name='id', op='lt', val=3)]
        url = '/api2/person?filter[objects]={0}'.format(dumps(filters))
        response = self.app.delete(url)
        assert response.status_code == 200
        document = loads(response.data)
        assert document['meta']['total'] == 2
        assert [person3] == self.session.query(self.Person).all()
