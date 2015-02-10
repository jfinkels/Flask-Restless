# -*- encoding: utf-8 -*-
"""
    tests.test_views
    ~~~~~~~~~~~~~~~~

    Provides unit tests for the :mod:`flask_restless.views` module.

    :copyright: 2011 by Lincoln de Sousa <lincoln@comum.org>
    :copyright: 2012, 2013, 2014, 2015 Jeffrey Finkelstein
                <jeffrey.finkelstein@gmail.com> and contributors.
    :license: GNU AGPLv3+ or BSD

"""
from datetime import date
from datetime import datetime
from datetime import timedelta
import math
from urllib.parse import quote as urlquote

import dateutil
from flask import json
try:
    from flask.ext.sqlalchemy import SQLAlchemy
except:
    has_flask_sqlalchemy = False
else:
    has_flask_sqlalchemy = True
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import func
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Unicode
from sqlalchemy.ext.associationproxy import association_proxy as prox
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship as rel
from sqlalchemy.orm.collections import column_mapped_collection as col_mapped

from flask.ext.restless.helpers import to_dict
from flask.ext.restless.manager import APIManager

from .helpers import FlaskTestBase
from .helpers import ManagerTestBase
from .helpers import skip_unless
from .helpers import TestSupport
from .helpers import TestSupportPrefilled
from .helpers import unregister_fsa_session_signals


dumps = json.dumps
loads = json.loads


#: The User-Agent string for Microsoft Internet Explorer 8.
#:
#: From <http://blogs.msdn.com/b/ie/archive/2008/02/21/the-internet-explorer-8-user-agent-string.aspx>.
MSIE8_UA = 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0)'

#: The User-Agent string for Microsoft Internet Explorer 9.
#:
#: From <http://blogs.msdn.com/b/ie/archive/2010/03/23/introducing-ie9-s-user-agent-string.aspx>.
MSIE9_UA = 'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)'


# @skip_unless(has_flask_sqlalchemy, 'Flask-SQLAlchemy not found.')
# class TestFSAModel(FlaskTestBase):
#     """Tests for functions which operate on Flask-SQLAlchemy models."""

#     def setUp(self):
#         """Creates the Flask-SQLAlchemy database and models."""
#         super(TestFSAModel, self).setUp()
#         self.db = SQLAlchemy(self.flaskapp)

#         class Person(self.db.Model):
#             id = self.db.Column(self.db.Integer, primary_key=True)

#         self.Person = Person
#         self.db.create_all()
#         self.manager = APIManager(self.flaskapp, flask_sqlalchemy_db=self.db)

#     def tearDown(self):
#         """Drops all tables."""
#         self.db.drop_all()
#         unregister_fsa_session_signals()

#     # def test_get(self):
#     #     """Test for the :meth:`views.API.get` method with models defined using
#     #     Flask-SQLAlchemy with both dynamically loaded and static relationships.

#     #     """
#     #     # create the API endpoint
#     #     self.manager.create_api(self.User)
#     #     self.manager.create_api(self.LazyUser)
#     #     self.manager.create_api(self.Pet)
#     #     self.manager.create_api(self.LazyPet)

#     #     response = self.app.get('/api/user')
#     #     assert 200 == response.status_code
#     #     response = self.app.get('/api/lazy_user')
#     #     assert 200 == response.status_code
#     #     response = self.app.get('/api/pet')
#     #     assert 200 == response.status_code
#     #     response = self.app.get('/api/lazy_pet')
#     #     assert 200 == response.status_code

#     #     # create a user with two pets
#     #     owner = self.User()
#     #     pet1 = self.Pet()
#     #     pet2 = self.Pet()
#     #     pet3 = self.Pet()
#     #     pet1.owner = owner
#     #     pet2.owner = owner
#     #     self.db.session.add_all([owner, pet1, pet2, pet3])
#     #     self.db.session.commit()

#     #     response = self.app.get('/api/user/{0:d}'.format(owner.id))
#     #     assert 200 == response.status_code
#     #     data = loads(response.data)
#     #     assert 2 == len(data['pets'])
#     #     for pet in data['pets']:
#     #         assert owner.id == pet['ownerid']

#     #     response = self.app.get('/api/pet/1')
#     #     assert 200 == response.status_code
#     #     data = loads(response.data)
#     #     assert not isinstance(data['owner'], list)
#     #     assert owner.id == data['ownerid']

#     #     # create a lazy user with two lazy pets
#     #     owner = self.LazyUser()
#     #     pet1 = self.LazyPet()
#     #     pet2 = self.LazyPet()
#     #     pet1.owner = owner
#     #     pet2.owner = owner
#     #     self.db.session.add_all([owner, pet1, pet2])
#     #     self.db.session.commit()

#     #     response = self.app.get('/api/lazy_user/{0:d}'.format(owner.id))
#     #     assert 200 == response.status_code
#     #     data = loads(response.data)
#     #     assert 2 == len(data['pets'])
#     #     for pet in data['pets']:
#     #         assert owner.id == pet['ownerid']

#     #     response = self.app.get('/api/lazy_pet/1')
#     #     assert 200 == response.status_code
#     #     data = loads(response.data)
#     #     assert not isinstance(data['owner'], list)
#     #     assert owner.id == data['ownerid']

#     #     # Check that it's possible to get owner if not null
#     #     response = self.app.get('/api/pet/1/owner')
#     #     assert 200 == response.status_code
#     #     data = loads(response.data)
#     #     assert 2 == len(data['pets'])
#     #     # And that we get a 404 if owner is null
#     #     response = self.app.get('/api/pet/3/owner')
#     #     assert 404 == response.status_code


class TestAPI(TestSupport):
    """Unit tests for the :class:`flask_restless.views.API` class."""

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`testapp.Person` and
        :class:`testapp.Computer` models.

        """
        # create the database
        super(TestAPI, self).setUp()

        # setup the URLs for the Person and Computer API
        self.manager.create_api(self.Person,
                                methods=['GET', 'PATCH', 'POST', 'DELETE'])
        self.manager.create_api(self.Computer,
                                methods=['GET', 'POST', 'PATCH'])

        # setup the URLs for the Car manufacturer API
        self.manager.create_api(self.CarManufacturer,
                                methods=['GET', 'PATCH', 'POST', 'DELETE'])
        self.manager.create_api(self.CarModel,
                                methods=['GET', 'PATCH', 'POST', 'DELETE'])

        self.manager.create_api(self.User, methods=['POST'],
                                primary_key='email')

        # to facilitate searching
        self.app.search = lambda url, q: self.app.get(url + '?q={0}'.format(q))

    # def test_post_invalid_json(self):
    #     # Invalid JSON in request data should respond with error.
    #     response = self.app.post('/api/person', data='Invalid JSON string')
    #     assert response.status_code == 400
    #     assert loads(response.data)['message'] == 'Unable to decode data'

    # def test_post_integrity_error(self):
    #     # Test the integrity exception by violating the unique 'name' field of
    #     # the Person model.
    #     person = dict(name=u'foo')
    #     response = self.app.post('/api/person', data=dumps(person))
    #     assert response.status_code == 201
    #     response = self.app.post('/api/person', data=dumps(person))
    #     assert response.status_code == 400
    #     assert loads(response.data)['message'] == 'IntegrityError'
    #     assert self.session.is_active, "Session is in `partial rollback` state"

    #     # For issue #158 we make sure that the previous failure is rolled back
    #     # so that we can add valid entries again
    #     person = dict(name=u'bar')
    #     response = self.app.post('/api/person', data=dumps(person))
    #     assert response.status_code == 201
    #     assert 'id' in loads(response.data)
    #     person = dict(name=u'bar')
    #     response = self.app.post('/api/person', data=dumps(person))
    #     assert response.status_code == 201
    #     assert 'id' in loads(response.data)

    #     response = self.app.get('/api/person/1')
    #     assert response.status_code == 200

    #     deep = {'computers': [], 'projects': []}
    #     person = self.session.query(self.Person).filter_by(id=1).first()
    #     inst = to_dict(person, deep)
    #     assert loads(response.data) == inst

    # def test_post_m2m(self):
    #     """Test for creating a new instance of the database model that has a
    #     many to many relation that uses an association object to allow extra
    #     info to be stored on the helper table.

    #     For more info, see issue #166.

    #     """
    #     vim = self.Program(name=u'Vim')
    #     emacs = self.Program(name=u'Emacs')
    #     self.session.add_all([vim, emacs])
    #     self.session.commit()
    #     data = {
    #         'vendor': u'Apple',
    #         'name': u'iMac',
    #         'programs': [
    #             {
    #                 'program_id': 1,
    #                 'licensed': False
    #             },
    #             {
    #                 'program_id': 2,
    #                 'licensed': True
    #             }
    #         ]
    #     }
    #     response = self.app.post('/api/computer', data=dumps(data))
    #     assert response.status_code == 201
    #     assert 'id' in loads(response.data)
    #     response = self.app.get('/api/computer/1')
    #     assert response.status_code == 200

    # def test_post_bad_parameter(self):
    #     """Tests that attempting to make a :http:method:`post` request with a
    #     form parameter which does not exist on the specified model responds
    #     with an error message.

    #     """
    #     response = self.app.post('/api/person', data=dumps(dict(bogus=0)))
    #     assert 400 == response.status_code

    #     response = self.app.post('/api/person',
    #                              data=dumps(dict(is_minor=True)))
    #     assert 400 == response.status_code

    # def test_post_nullable_date(self):
    #     """Tests the creation of a model with a nullable date field."""
    #     self.manager.create_api(self.Star, methods=['GET', 'POST'])
    #     data = dict(inception_time=None)
    #     response = self.app.post('/api/star', data=dumps(data))
    #     assert response.status_code == 201
    #     response = self.app.get('/api/star/1')
    #     assert response.status_code == 200
    #     assert loads(response.data)['inception_time'] is None

    # def test_post_empty_date(self):
    #     """Tests that attempting to assign an empty date string to a date field
    #     actually assigns a value of ``None``.

    #     """
    #     self.manager.create_api(self.Star, methods=['GET', 'POST'])
    #     data = dict(inception_time='')
    #     response = self.app.post('/api/star', data=dumps(data))
    #     assert response.status_code == 201
    #     response = self.app.get('/api/star/1')
    #     assert response.status_code == 200
    #     assert loads(response.data)['inception_time'] is None

    # def test_post_date_functions(self):
    #     """Tests that ``'CURRENT_TIMESTAMP'`` gets converted into a datetime
    #     object when making a request to set a date or time field.

    #     """
    #     self.manager.create_api(self.Star, methods=['GET', 'POST'])
    #     data = dict(inception_time='CURRENT_TIMESTAMP')
    #     response = self.app.post('/api/star', data=dumps(data))
    #     assert response.status_code == 201
    #     response = self.app.get('/api/star/1')
    #     assert response.status_code == 200
    #     inception_time = loads(response.data)['inception_time']
    #     assert inception_time is not None
    #     inception_time = dateutil.parser.parse(inception_time)
    #     diff = datetime.utcnow() - inception_time
    #     assert diff.days == 0
    #     assert (diff.seconds + diff.microseconds / 1000000.0) < 3600

    # def test_post_interval_functions(self):
    #     oldJSONEncoder = self.flaskapp.json_encoder

    #     class IntervalJSONEncoder(oldJSONEncoder):
    #         def default(self, obj):
    #             if isinstance(obj, timedelta):
    #                 return int(obj.days * 86400 + obj.seconds)
    #             return oldJSONEncoder.default(self, obj)

    #     self.flaskapp.json_encoder = IntervalJSONEncoder

    #     self.manager.create_api(self.Satellite, methods=['GET', 'POST'])
    #     data = dict(name="Callufrax_Minor", period=300)
    #     response = self.app.post('/api/satellite', data=dumps(data))
    #     assert response.status_code == 201
    #     response = self.app.get('/api/satellite/Callufrax_Minor')
    #     assert response.status_code == 200
    #     assert loads(response.data)['period'] == 300
    #     satellite = self.session.query(self.Satellite).first()
    #     assert satellite.period == timedelta(0, 300)

    # def test_post_with_submodels(self):
    #     """Tests the creation of a model with a related field."""
    #     data = {'name': u'John', 'age': 2041,
    #             'computers': [{'name': u'lixeiro', 'vendor': u'Lemote'}]}
    #     response = self.app.post('/api/person', data=dumps(data))
    #     assert response.status_code == 201
    #     assert 'id' in loads(response.data)

    #     response = self.app.get('/api/person')
    #     assert len(loads(response.data)['objects']) == 1

    #     # Test with nested objects
    #     data = {'name': 'Rodriguez', 'age': 70,
    #             'computers': [{'name': 'iMac', 'vendor': 'Apple',
    #                            'programs': [{'program': {'name': 'iPhoto'}}]}]}
    #     response = self.app.post('/api/person', data=dumps(data))
    #     assert 201 == response.status_code
    #     response = self.app.get('/api/computer/2/programs')
    #     programs = loads(response.data)['objects']
    #     assert programs[0]['program']['name'] == 'iPhoto'

    # def test_post_unicode_primary_key(self):
    #     """Test for creating a new instance of the database model using the
    #     :http:method:`post` method with a Unicode primary key.

    #     """
    #     response = self.app.post('/api/user', data=dumps({'id': 1,
    #                                                       'email': u'Юникод'}))
    #     assert response.status_code == 201

    # def test_post_with_single_submodel(self):
    #     data = {'vendor': u'Apple',  'name': u'iMac',
    #             'owner': {'name': u'John', 'age': 2041}}
    #     response = self.app.post('/api/computer', data=dumps(data))
    #     assert response.status_code == 201
    #     assert 'id' in loads(response.data)
    #     # Test if owner was successfully created
    #     response = self.app.get('/api/person')
    #     assert len(loads(response.data)['objects']) == 1

    def test_patch_update_relations(self):
        """Test for posting a new model and simultaneously adding related
        instances *and* updating information on those instances.

        For more information see issue #164.

        """
        # First, create a new computer object with an empty `name` field and a
        # new person with no related computers.
        response = self.app.post('/api/computer', data=dumps({}))
        assert 201 == response.status_code
        response = self.app.post('/api/person', data=dumps({}))
        assert 201 == response.status_code
        # Second, patch the person by setting its list of related computer
        # instances to include the previously created computer, *and*
        # simultaneously update the `name` attribute of that computer.
        data = dict(computers=[dict(id=1, name='foo')])
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert 200 == response.status_code
        # Check that the computer now has its `name` field set.
        response = self.app.get('/api/computer/1')
        assert 200 == response.status_code
        assert 'foo' == loads(response.data)['name']
        # Add a new computer by patching person
        data = {'computers': [{'id': 1},
                              {'name': 'iMac', 'vendor': 'Apple',
                               'programs': [{'program': {'name': 'iPhoto'}}]}]}
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert 200 == response.status_code
        response = self.app.get('/api/computer/2/programs')
        programs = loads(response.data)['objects']
        assert programs[0]['program']['name'] == 'iPhoto'
        # Add a program to the computer through the person
        data = {'computers': [{'id': 1},
                              {'id': 2,
                               'programs': [{'program_id': 1},
                                            {'program': {'name': 'iMovie'}}]}]}
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert 200 == response.status_code
        response = self.app.get('/api/computer/2/programs')
        programs = loads(response.data)['objects']
        assert programs[1]['program']['name'] == 'iMovie'

    def test_patch_m2m(self):
        """Test for updating a model with a many to many relation that uses
        an association object to allow extra data to be stored in the helper
        table.

        For more info, see issue #166

        """
        response = self.app.post('/api/computer', data=dumps({}))
        assert 201 == response.status_code
        vim = self.Program(name=u'Vim')
        emacs = self.Program(name=u'Emacs')
        self.session.add_all([vim, emacs])
        self.session.commit()
        data = {
            'programs': {
                'add': [
                    {
                        'program_id': 1,
                        'licensed': False
                    }
                ]
            }
        }
        response = self.app.patch('/api/computer/1', data=dumps(data))
        computer = loads(response.data)
        assert 200 == response.status_code
        vim_relation = {
            'computer_id': 1,
            'program_id': 1,
            'licensed': False
        }
        assert vim_relation in computer['programs']
        data = {
            'programs': {
                'add': [
                    {
                        'program_id': 2,
                        'licensed': True
                    }
                ]
            }
        }
        response = self.app.patch('/api/computer/1', data=dumps(data))
        computer = loads(response.data)
        assert 200 == response.status_code
        emacs_relation = {
            'computer_id': 1,
            'program_id': 2,
            'licensed': True
        }
        assert emacs_relation in computer['programs']
        vim_relation = {
            'computer_id': 1,
            'program_id': 1,
            'licensed': False
        }
        assert vim_relation in computer['programs']

    def test_patch_remove_m2m(self):
        """Test for removing a relation on a model that uses an association
        object to allow extra data to be stored in the helper table.

        For more info, see issue #166

        """
        response = self.app.post('/api/computer', data=dumps({}))
        assert 201 == response.status_code
        vim = self.Program(name=u'Vim')
        emacs = self.Program(name=u'Emacs')
        self.session.add_all([vim, emacs])
        self.session.commit()
        data = {
            'programs': [
                {
                    'program_id': 1,
                    'licensed': False
                },
                {
                    'program_id': 2,
                    'licensed': True
                }
            ]
        }
        response = self.app.patch('/api/computer/1', data=dumps(data))
        computer = loads(response.data)
        assert 200 == response.status_code
        vim_relation = {
            'computer_id': 1,
            'program_id': 1,
            'licensed': False
        }
        emacs_relation = {
            'computer_id': 1,
            'program_id': 2,
            'licensed': True
        }
        assert vim_relation in computer['programs']
        assert emacs_relation in computer['programs']
        data = {
            'programs': {
                'remove': [{'program_id': 1}]
            }
        }
        response = self.app.patch('/api/computer/1', data=dumps(data))
        computer = loads(response.data)
        assert 200 == response.status_code
        assert vim_relation not in computer['programs']
        assert emacs_relation in computer['programs']

    def test_patch_integrity_error(self):
        self.session.add(self.Person(name=u"Waldorf", age=89))
        self.session.add(self.Person(name=u"Statler", age=91))
        self.session.commit()

        # This errors as expected
        response = self.app.patch('/api/person/1',
                                  data=dumps({'name': u'Statler'}))
        assert response.status_code == 400
        assert json.loads(response.data)['message'] == 'IntegrityError'
        assert self.session.is_active, "Session is in `partial rollback` state"

    def test_delete(self):
        """Test for deleting an instance of the database using the
        :http:method:`delete` method.

        """
        # Creating the person who's gonna be deleted
        response = self.app.post('/api/person',
                                 data=dumps({'name': u'Lincoln', 'age': 23}))
        assert response.status_code == 201
        assert 'id' in loads(response.data)

        # Making sure it has been created
        deep = {'computers': [], 'projects': []}
        person = self.session.query(self.Person).filter_by(id=1).first()
        inst = to_dict(person, deep)
        response = self.app.get('/api/person/1')
        assert loads(response.data) == inst

        # Deleting it
        response = self.app.delete('/api/person/1')
        assert response.status_code == 204

        # Making sure it has been deleted
        people = self.session.query(self.Person).filter_by(id=1)
        assert people.count() == 0

    def test_disallow_delete_many(self):
        """Tests for deleting many instances of a collection by using a search
        query to select instances to delete.

        """
        # Don't allow deleting many unless explicitly requested.
        response = self.app.delete('/api/person')
        assert response.status_code == 405

    def test_delete_many(self):
        """Tests for deleting many instances of a collection by using a search
        query to select instances to delete.

        """
        # Recreate the API to allow delete many at /api2/person.
        self.manager.create_api(self.Person, methods=['DELETE'],
                                allow_delete_many=True, url_prefix='/api2')
        person1 = self.Person(name=u'foo')
        person2 = self.Person(name=u'bar')
        person3 = self.Person(name=u'baz')
        self.session.add_all([person1, person2, person3])
        self.session.commit()

        search = {'filters': [{'name': 'name', 'val': 'ba%', 'op': 'like'}]}
        response = self.app.delete('/api2/person?q={0}'.format(dumps(search)))
        assert response.status_code == 200
        data = loads(response.data)
        assert data['num_deleted'] == 2

    def test_delete_integrity_error(self):
        """Tests that an :exc:`IntegrityError` raised in a
        :http:method:`delete` request is caught and returned to the client
        safely.

        """
        # TODO Fill me in.
        pass

    def test_delete_absent_instance(self):
        """Test that deleting an instance of the model which does not exist
        fails.

        This should give us a 404 when the object is not found.

        """
        response = self.app.delete('/api/person/1')
        assert response.status_code == 404

    def test_disallow_patch_many(self):
        """Tests that disallowing "patch many" requests responds with a
        :http:statuscode:`405`.

        """
        response = self.app.patch('/api/person', data=dumps(dict(name='foo')))
        assert response.status_code == 405

    def test_put_same_as_patch(self):
        """Tests that :http:method:`put` requests are the same as
        :http:method:`patch` requests.

        """
        # recreate the api to allow patch many at /api/v2/person
        self.manager.create_api(self.Person, methods=['GET', 'POST', 'PUT'],
                                allow_patch_many=True, url_prefix='/api/v2')

        # Creating some people
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Lincoln', 'age': 23}))
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Lucy', 'age': 23}))
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Mary', 'age': 25}))

        # change a single entry
        resp = self.app.put('/api/v2/person/1', data=dumps({'age': 24}))
        assert resp.status_code == 200

        resp = self.app.get('/api/v2/person/1')
        assert resp.status_code == 200
        assert loads(resp.data)['age'] == 24

        # Changing the birth date field of the entire collection
        day, month, year = 15, 9, 1986
        birth_date = date(year, month, day).strftime('%d/%m/%Y')  # iso8601
        form = {'birth_date': birth_date}
        self.app.put('/api/v2/person', data=dumps(form))

        # Finally, testing if the change was made
        response = self.app.get('/api/v2/person')
        loaded = loads(response.data)['objects']
        for i in loaded:
            expected = '{0:4d}-{1:02d}-{2:02d}'.format(year, month, day)
            assert i['birth_date'] == expected

    def test_patch_empty(self):
        """Test for making a :http:method:`patch` request with no data."""
        response = self.app.post('/api/person', data=dumps(dict(name='foo')))
        assert response.status_code == 201
        personid = loads(response.data)['id']
        # here we really send no data
        response = self.app.patch('/api/person/' + str(personid))
        assert response.status_code == 400
        # here we send the empty string (which is not valid JSON)
        response = self.app.patch('/api/person/' + str(personid), data='')
        assert response.status_code == 400

    def test_patch_bad_parameter(self):
        """Tests that attempting to make a :http:method:`patch` request with a
        form parameter which does not exist on the specified model responds
        with an error message.

        """
        response = self.app.post('/api/person', data=dumps({}))
        assert 201 == response.status_code
        response = self.app.patch('/api/person/1', data=dumps(dict(bogus=0)))
        assert 400 == response.status_code
        response = self.app.patch('/api/person/1',
                                  data=dumps(dict(is_minor=True)))
        assert 400 == response.status_code

    def test_patch_many(self):
        """Test for updating a collection of instances of the model using the
        :http:method:`patch` method.

        """
        # recreate the api to allow patch many at /api/v2/person
        self.manager.create_api(self.Person, methods=['GET', 'POST', 'PATCH'],
                                allow_patch_many=True, url_prefix='/api/v2')

        # Creating some people
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Lincoln', 'age': 23}))
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Lucy', 'age': 23}))
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Mary', 'age': 25}))

        # Trying to pass invalid data to the update method
        resp = self.app.patch('/api/v2/person', data='Hello there')
        assert resp.status_code == 400
        assert loads(resp.data)['message'] == 'Unable to decode data'

        # Changing the birth date field of the entire collection
        day, month, year = 15, 9, 1986
        birth_date = date(year, month, day).strftime('%d/%m/%Y')  # iso8601
        form = {'birth_date': birth_date}
        self.app.patch('/api/v2/person', data=dumps(form))

        # Finally, testing if the change was made
        response = self.app.get('/api/v2/person')
        loaded = loads(response.data)['objects']
        for i in loaded:
            expected = '{0:4d}-{1:02d}-{2:02d}'.format(year, month, day)
            assert i['birth_date'] == expected

    def test_patch_many_with_filter(self):
        """Test for updating a collection of instances of the model using a
        :http:method:patch request with filters.

        """
        # recreate the api to allow patch many at /api/v2/person
        self.manager.create_api(self.Person, methods=['GET', 'POST', 'PATCH'],
                                allow_patch_many=True, url_prefix='/api/v2')
        # Creating some people
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Lincoln', 'age': 23}))
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Lucy', 'age': 23}))
        self.app.post('/api/v2/person',
                      data=dumps({'name': u'Mary', 'age': 25}))
        search = {'filters': [{'name': 'name', 'val': u'Lincoln',
                               'op': 'equals'}]}
        # Changing the birth date field for objects where name field equals
        # Lincoln
        day, month, year = 15, 9, 1986
        birth_date = date(year, month, day).strftime('%d/%m/%Y')  # iso8601
        form = {'birth_date': birth_date, 'q': search}
        response = self.app.patch('/api/v2/person', data=dumps(form))
        num_modified = loads(response.data)['num_modified']
        assert num_modified == 1

    def test_single_update(self):
        """Test for updating a single instance of the model using the
        :http:method:`patch` method.

        """
        resp = self.app.post('/api/person', data=dumps({'name': u'Lincoln',
                                                        'age': 10}))
        assert resp.status_code == 201
        assert 'id' in loads(resp.data)

        # Trying to pass invalid data to the update method
        resp = self.app.patch('/api/person/1', data='Invalid JSON string')
        assert resp.status_code == 400
        assert loads(resp.data)['message'] == 'Unable to decode data'

        resp = self.app.patch('/api/person/1', data=dumps({'age': 24}))
        assert resp.status_code == 200

        resp = self.app.get('/api/person/1')
        assert resp.status_code == 200
        assert loads(resp.data)['age'] == 24

    def test_patch_404(self):
        """Tests that making a :http:method:`patch` request to an instance
        which does not exist results in a :http:statuscode:`404`.

        """
        resp = self.app.patch('/api/person/1', data=dumps(dict(name='foo')))
        assert resp.status_code == 404

    def test_patch_with_single_submodel(self):
        # Create a new object with a single submodel
        data = {'vendor': u'Apple', 'name': u'iMac',
                'owner': {'name': u'John', 'age': 2041}}
        response = self.app.post('/api/computer', data=dumps(data))
        assert response.status_code == 201
        data = loads(response.data)
        assert 1 == data['owner']['id']
        assert u'John' == data['owner']['name']
        assert 2041 == data['owner']['age']

        # Update the submodel
        data = {'id': 1, 'owner': {'id': 1, 'age': 29}}
        response = self.app.patch('/api/computer/1', data=dumps(data))
        assert response.status_code == 200
        data = loads(response.data)

        assert u'John' == data['owner']['name']
        assert 29 == data['owner']['age']

    def test_patch_set_submodel(self):
        """Test for assigning a list to a relation of a model using
        :http:method:`patch`.

        """
        # create the person
        response = self.app.post('/api/person', data=dumps({}))
        assert response.status_code == 201

        # patch the person with some computers
        data = {'computers': [{'name': u'lixeiro', 'vendor': u'Lemote'},
                              {'name': u'foo', 'vendor': u'bar'}]}
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert 200 == response.status_code
        data = loads(response.data)
        assert 2 == len(data['computers'])
        assert u'lixeiro' == data['computers'][0]['name']
        assert u'Lemote' == data['computers'][0]['vendor']
        assert u'foo' == data['computers'][1]['name']
        assert u'bar' == data['computers'][1]['vendor']

        # change one of the computers
        data = {'computers': [{'id': data['computers'][0]['id']},
                              {'id': data['computers'][1]['id'],
                               'vendor': u'Apple'}]}
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert 200 == response.status_code
        data = loads(response.data)
        assert 2 == len(data['computers'])
        assert u'lixeiro' == data['computers'][0]['name']
        assert u'Lemote' == data['computers'][0]['vendor']
        assert u'foo' == data['computers'][1]['name']
        assert u'Apple' == data['computers'][1]['vendor']

        # patch the person with some new computers
        data = {'computers': [{'name': u'hey', 'vendor': u'you'},
                              {'name': u'big', 'vendor': u'money'},
                              {'name': u'milk', 'vendor': u'chocolate'}]}
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert 200 == response.status_code
        data = loads(response.data)
        assert 3 == len(data['computers'])
        assert u'hey' == data['computers'][0]['name']
        assert u'big' == data['computers'][1]['name']
        assert u'milk' == data['computers'][2]['name']

    def test_patch_duplicate(self):
        """Test for assigning a list containing duplicate items
        to a relation of a model using :http:method:`patch`.

        """
        # create the manufacturer with a duplicate car
        data = {'name': u'Ford', 'models': [{'name': u'Maverick', 'seats': 2},
                                            {'name': u'Mustang', 'seats': 4},
                                            {'name': u'Maverick', 'seats': 2}]}
        response = self.app.post('/api/car_manufacturer', data=dumps(data))
        assert response.status_code == 201
        responsedata = loads(response.data)
        assert 3 == len(data['models'])
        assert u'Maverick' == responsedata['models'][0]['name']
        assert u'Mustang' == responsedata['models'][1]['name']
        assert u'Maverick' == responsedata['models'][2]['name']

        # add another duplicate car
        data['models'].append({'name': u'Mustang', 'seats': 4})
        response = self.app.patch('/api/car_manufacturer/1', data=dumps(data))
        assert response.status_code == 200
        data = loads(response.data)
        assert 4 == len(data['models'])
        assert u'Maverick' == data['models'][0]['name']
        assert u'Mustang' == data['models'][1]['name']
        assert u'Maverick' == data['models'][2]['name']
        assert u'Mustang' == data['models'][3]['name']

    def test_patch_new_single(self):
        """Test for adding a single new object to a one-to-one relationship
        using :http:method:`patch`.

        """
        # create the person
        data = {'name': u'Lincoln', 'age': 23}
        response = self.app.post('/api/person', data=dumps(data))
        assert response.status_code == 201

        # patch the person with a new computer
        data = {'computers': {'add': {'name': u'lixeiro',
                                      'vendor': u'Lemote'}}}

        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 200

        # Let's check it out
        response = self.app.get('/api/person/1')
        loaded = loads(response.data)

        assert len(loaded['computers']) == 1
        assert loaded['computers'][0]['name'] == \
            data['computers']['add']['name']
        assert loaded['computers'][0]['vendor'] == \
            data['computers']['add']['vendor']

        # test that this new computer was added to the database as well
        computer = self.session.query(self.Computer).filter_by(id=1).first()
        assert computer is not None
        assert data['computers']['add']['name'] == computer.name
        assert data['computers']['add']['vendor'] == computer.vendor

    def test_patch_existing_single(self):
        """Test for adding a single existing object to a one-to-one
        relationship using :http:method:`patch`.

        """
        # create the person
        data = {'name': u'Lincoln', 'age': 23}
        response = self.app.post('/api/person', data=dumps(data))
        assert response.status_code == 201

        # create the computer
        data = {'name': u'lixeiro', 'vendor': u'Lemote'}
        response = self.app.post('/api/computer', data=dumps(data))
        assert response.status_code == 201

        # patch the person with the created computer
        data = {'computers': {'add': {'id': 1}}}
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 200

        # Let's check it out
        response = self.app.get('/api/person/1')
        loaded = loads(response.data)

        assert len(loaded['computers']) == 1
        assert loaded['computers'][0]['id'] == data['computers']['add']['id']

    def test_patch_add_submodels(self):
        """Test for updating a single instance of the model by adding a list of
        related models using the :http:method:`patch` method.

        """
        data = dict(name=u'Lincoln', age=23)
        response = self.app.post('/api/person', data=dumps(data))
        assert response.status_code == 201

        add1 = {'name': u'lixeiro', 'vendor': u'Lemote'}
        add2 = {'name': u'foo', 'vendor': u'bar'}
        data = {'computers': {'add': [add1, add2]}}
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 200
        response = self.app.get('/api/person/1')
        loaded = loads(response.data)

        assert len(loaded['computers']) == 2
        assert loaded['computers'][0]['name'] == u'lixeiro'
        assert loaded['computers'][0]['vendor'] == u'Lemote'
        assert loaded['computers'][1]['name'] == u'foo'
        assert loaded['computers'][1]['vendor'] == u'bar'

        # test that these new computers were added to the database as well
        computer = self.session.query(self.Computer).filter_by(id=1).first()
        assert computer is not None
        assert u'lixeiro' == computer.name
        assert u'Lemote' == computer.vendor
        computer = self.session.query(self.Computer).filter_by(id=2).first()
        assert computer is not None
        assert u'foo' == computer.name
        assert u'bar' == computer.vendor

    def test_patch_remove_submodel(self):
        """Test for updating a single instance of the model by removing a
        related model using the :http:method:`patch` method.

        """
        # Creating the row that will be updated
        data = {
            'name': u'Lincoln', 'age': 23,
            'computers': [
                {'name': u'lixeiro', 'vendor': u'Lemote'},
                {'name': u'pidinti', 'vendor': u'HP'},
            ],
        }
        self.app.post('/api/person', data=dumps(data))

        # Data for the update
        update_data = {
            'computers': {
                'remove': [{'name': u'pidinti'}],
            }
        }
        resp = self.app.patch('/api/person/1', data=dumps(update_data))
        assert resp.status_code == 200
        assert loads(resp.data)['id'] == 1

        # Let's check it out
        response = self.app.get('/api/person/1')
        loaded = loads(response.data)
        assert len(loaded['computers']) == 1

    def test_patch_autodelete_submodel(self):
        """Tests the automatic deletion of entries marked with the
        ``__delete__`` flag on an update operation.

        It also tests adding an already created instance as a related item.

        """
        # Creating all rows needed in our test
        person_data = {'name': u'Lincoln', 'age': 23}
        resp = self.app.post('/api/person', data=dumps(person_data))
        assert resp.status_code == 201
        comp_data = {'name': u'lixeiro', 'vendor': u'Lemote'}
        resp = self.app.post('/api/computer', data=dumps(comp_data))
        assert resp.status_code == 201

        # updating person to add the computer
        update_data = {'computers': {'add': [{'id': 1}]}}
        self.app.patch('/api/person/1', data=dumps(update_data))

        # Making sure that everything worked properly
        resp = self.app.get('/api/person/1')
        assert resp.status_code == 200
        loaded = loads(resp.data)
        assert len(loaded['computers']) == 1
        assert loaded['computers'][0]['name'] == u'lixeiro'

        # Now, let's remove it and delete it
        update2_data = {
            'computers': {
                'remove': [
                    {'id': 1, '__delete__': True},
                ],
            },
        }
        resp = self.app.patch('/api/person/1', data=dumps(update2_data))
        assert resp.status_code == 200

        # Testing to make sure it was removed from the related field
        resp = self.app.get('/api/person/1')
        assert resp.status_code == 200
        loaded = loads(resp.data)
        assert len(loaded['computers']) == 0

        # Making sure it was removed from the database
        resp = self.app.get('/api/computer/1')
        assert resp.status_code == 404

    def test_num_results(self):
        """Tests that a request for (a subset of) all instances of a model
        includes the total number of results as part of the JSON response.

        """
        self.manager.create_api(self.Person)
        for i in range(15):
            d = dict(name='person{0}'.format(i))
            response = self.app.post('/api/person', data=dumps(d))
            assert response.status_code == 201
        response = self.app.get('/api/person')
        assert response.status_code == 200
        data = loads(response.data)
        assert data['meta']['num_results'] == 15

    # def test_post_form_preprocessor(self):
    #     """Tests POST method decoration using a custom function."""
    #     def decorator_function(data=None, **kw):
    #         if data:
    #             data['other'] = 7

    #     # test for function that decorates parameters with 'other' attribute
    #     self.manager.create_api(self.Person, methods=['POST'],
    #                             url_prefix='/api/v2',
    #                             post_form_preprocessor=decorator_function)

    #     response = self.app.post('/api/v2/person',
    #                              data=dumps({'name': u'Lincoln', 'age': 23}))
    #     assert response.status_code == 201

    #     personid = loads(response.data)['id']
    #     person = self.session.query(self.Person).filter_by(id=personid).first()
    #     assert person.other == 7

    # def test_duplicate_post(self):
    #     """Tests for making a :http:method:`post` request with data that
    #     already exists in the database.

    #     """
    #     data = dict(name='test')
    #     response = self.app.post('/api/person', data=dumps(data))
    #     assert 201 == response.status_code
    #     response = self.app.post('/api/person', data=dumps(data))
    #     assert 400 == response.status_code

    def test_delete_from_relation(self):
        """Tests that a :http:method:`delete` request to a related instance
        removes that related instance from the specified model.

        See issue #193.

        """
        person = self.Person()
        computer = self.Computer()
        person.computers.append(computer)
        self.session.add_all((person, computer))
        self.session.commit()
        # Delete the related computer.
        response = self.app.delete('/api/person/1/computers/1')
        assert response.status_code == 204
        # Check that it is actually gone from the relation.
        response = self.app.get('/api/person/1')
        assert response.status_code == 200
        assert len(loads(response.data)['computers']) == 0
        # Check that the related instance hasn't been deleted from the database
        # altogether.
        response = self.app.get('/api/computer/1')
        assert response.status_code == 200

        # # Add the computer back in to the relation and use the Delete-Orphan
        # # header to instruct the server to delete the orphaned computer
        # # instance.
        # person.computers.append(computer)
        # self.session.commit()
        # response = self.app.delete('/api/person/1/computers/1',
        #                            headers={'Delete-Orphan': 1})
        # assert response.status_code == 204
        # response = self.app.get('/api/person/1/computers')
        # assert response.status_code == 200
        # assert len(loads(response.data)['computers']) == 0
        # response = self.app.get('/api/computers')
        # assert response.status_code == 200
        # assert len(loads(response.data)['objects']) == 0

    def test_set_hybrid_property(self):
        """Tests that a hybrid property can be correctly set by a client."""

        class HybridPerson(self.Person):

            @hybrid_property
            def abs_other(self):
                return self.other is not None and abs(self.other) or 0

            @abs_other.expression
            def abs_other(self):
                return func.sum(HybridPerson.other)

            @abs_other.setter
            def abs_other(self, v):
                self.other = v

            @hybrid_property
            def sq_other(self):
                if not isinstance(self.other, float):
                    return None

                return self.other ** 2

            @sq_other.setter
            def sq_other(self, v):
                self.other = math.sqrt(v)

        self.manager.create_api(HybridPerson, methods=['POST', 'PATCH'],
                                collection_name='hybrid')
        response = self.app.post('/api/hybrid', data=dumps({'abs_other': 1}))
        assert 201 == response.status_code
        data = loads(response.data)
        assert 1 == data['other']
        assert 1 == data['abs_other']

        response = self.app.post('/api/hybrid', data=dumps({'name': u'Rod'}))
        assert 201 == response.status_code
        response = self.app.patch('/api/hybrid/2', data=dumps({'sq_other': 4}))
        assert 200 == response.status_code
        data = loads(response.data)
        assert 2 == data['other']
        assert 4 == data['sq_other']

    def test_patch_with_hybrid_property(self):
        """Tests that a hybrid property can be correctly posted from a client.

        """
        self.session.add(self.Screen(id=1, width=5, height=4))
        self.session.commit()
        self.manager.create_api(self.Screen, methods=['PATCH'],
                                collection_name='screen')
        response = self.app.patch('/api/screen/1',
                                  data=dumps({"number_of_pixels": 50}))
        assert 200 == response.status_code
        data = loads(response.data)
        assert 5 == data['width']
        assert 10 == data['height']
        assert 50 == data['number_of_pixels']

    def test_like(self):
        """Tests for the like operator."""
        person1 = self.Person(name='foo')
        person2 = self.Person(name='bar')
        self.session.add_all([person1, person2])
        self.session.commit()
        data = dict(filters=[dict(name='name', op='like', val='%bar%')])
        response = self.app.search('/api/person', urlquote(dumps(data)))
        data = loads(response.data)
        people = data['objects']
        assert ['bar'] == sorted(person['name'] for person in people)


class TestAssociationProxy(ManagerTestBase):
    """Unit tests for models which have a relationship involving an association
    proxy.

    """

    def setUp(self):
        """Creates example models which are related by an association proxy
        table.

        """
        super(TestAssociationProxy, self).setUp()

        tag_product = Table('tag_product', self.Base.metadata,
                            Column('tag_id', Integer,
                                   ForeignKey('tag.id'),
                                   primary_key=True),
                            Column('product_id', Integer,
                                   ForeignKey('product.id'),
                                   primary_key=True))

        # Metadata is a key-value pair, used to test for association
        # proxies that use AssociationDict types
        # this is the association table for Image->metadata
        product_meta = Table('product_meta', self.Base.metadata,
                             Column('image_id', Integer,
                                    ForeignKey('image.id')),
                             Column('meta_id', Integer, ForeignKey('meta.id')))

        # For brevity, create this association proxy creator functions here.
        creator1 = lambda product: ChosenProductImage(product=product)
        creator2 = lambda image: ChosenProductImage(image=image)
        creator3 = lambda key, value: Metadata(key, value)

        class Metadata(self.Base):
            def __init__(self, key, value):
                super(Metadata, self).__init__()
                self.key = key
                self.value = value

            __tablename__ = 'meta'
            id = Column(Integer, primary_key=True)
            key = Column(String(256), nullable=False)
            value = Column(String(256))

        class Image(self.Base):
            __tablename__ = 'image'
            id = Column(Integer, primary_key=True)
            products = prox('chosen_product_images', 'product',
                            creator=creator1)

            meta_store = rel('Metadata',
                             cascade='all',
                             backref=backref(name='metadata'),
                             collection_class=col_mapped(Metadata.__table__.c.key),
                             secondary=lambda: product_meta)
            meta = prox('meta_store', 'value', creator=creator3)

        class ChosenProductImage(self.Base):
            __tablename__ = 'chosen_product_image'
            product_id = Column(Integer, ForeignKey('product.id'),
                                primary_key=True)
            image_id = Column(Integer, ForeignKey('image.id'),
                              primary_key=True)
            image = rel('Image', backref=backref(name='chosen_product_images',
                                                 cascade="all, delete-orphan"),
                        enable_typechecks=False)
            name = Column(Unicode, default=lambda: u'default name')

        class Tag(self.Base):
            __tablename__ = 'tag'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode, nullable=False)

        class Product(self.Base):
            __tablename__ = 'product'
            id = Column(Integer, primary_key=True)
            chosen_product_images = rel(ChosenProductImage,
                                        backref=backref(name='product'),
                                        cascade="all, delete-orphan")
            chosen_images = prox('chosen_product_images', 'image',
                                 creator=creator2)
            image_names = prox('chosen_product_images', 'name')
            tags = rel(Tag, secondary=tag_product, lazy='joined',
                       backref=backref(name='products', lazy='dynamic'))
            tag_names = prox('tags', 'name',
                             creator=lambda tag_name: Tag(name=tag_name))

        self.Product = Product
        self.Image = Image
        self.ChosenProductImage = ChosenProductImage
        self.Tag = Tag

        # create all the tables required for the models
        self.Base.metadata.create_all()

        # create the API endpoints
        self.manager.create_api(self.Product, methods=['GET', 'PATCH', 'POST'],
                                url_prefix='/api')
        self.manager.create_api(self.Image, methods=['GET', 'PATCH', 'POST'],
                                url_prefix='/api')

    def tearDown(self):
        """Drops all tables from the temporary database."""
        self.Base.metadata.drop_all()

    def _check_relations(self):
        """Makes :http:method:`get` requests for the product with ID 1 and the
        image with ID 1, ensuring that each has a relationship with the other
        via the association proxy table.

        """
        response = self.app.get('/api/product/1')
        data = loads(response.data)
        assert 'chosen_images' in data
        assert {'id': 1} in data['chosen_images']

        response = self.app.get('/api/image/1')
        data = loads(response.data)
        assert 'products' in data
        assert {'id': 1} in data['products']

    def _check_meta_relation(self):
        response = self.app.get('/api/image/1')
        data = loads(response.data)
        assert 'meta_store' in data
        assert 'file type' in data['meta_store']

    def _check_relations_two(self):
        """Makes :http:method:`get` requests for the product with ID 1 and the
        images with ID 1 and 2, ensuring that the product has a relationship
        with each image, and each image has a relationship with the product.

        """
        response = self.app.get('/api/product/1')
        data = loads(response.data)
        assert 'chosen_images' in data

        expected_chosen_project_images = [
            {'image_id': 1, 'product_id': 1, 'name': 'default name'},
            {'image_id': 2, 'product_id': 1, 'name': 'default name'}
        ]

        assert data['chosen_images'], [{'id': 1} == {'id': 2}]
        assert data['chosen_product_images'] == expected_chosen_project_images

        response = self.app.get('/api/image/1')
        data = loads(response.data)
        assert 'products' in data
        assert {'id': 1} in data['products']

        response = self.app.get('/api/image/2')
        data = loads(response.data)
        assert 'products' in data
        assert {'id': 1} in data['products']

    def test_assoc_dict_put(self):
        data = {'products': [{'id': 1}],
                'meta': [{'key': 'file type', 'value': 'png'}]}
        response = self.app.post('/api/image', data=dumps(data))
        assert response.status_code == 201

        self._check_meta_relation()

    def test_get_data(self):
        """Tests that a :http:method:`get` request exhibits the correct
        associations.

        """
        self.session.add(self.Product())
        self.session.add(self.Image())
        self.session.add(self.ChosenProductImage(image_id=1, product_id=1))
        self.session.commit()

        self._check_relations()

    def test_post(self):
        """Tests that a :http:method:`post` request correctly adds an
        association.

        """
        self.session.add(self.Product())
        self.session.commit()

        data = {'products': [{'id': 1}]}
        response = self.app.post('/api/image', data=dumps(data))
        assert response.status_code == 201

        self._check_relations()

    def test_post_many(self):
        """Tests that a :http:method:`post` request correctly adds multiple
        associations.

        """
        self.session.add(self.Image())
        self.session.add(self.Image())
        self.session.commit()

        data = {'chosen_images': [{'id': 1}, {'id': 2}]}
        response = self.app.post('/api/product', data=dumps(data))
        assert response.status_code == 201

        self._check_relations_two()

    def test_patch(self):
        """Tests that a :http:method:`patch` request correctly sets the
        appropriate associations.

        """
        self.session.add(self.Product())
        self.session.add(self.Image())
        self.session.commit()

        data = {'chosen_images': [{'id': 1}]}
        response = self.app.patch('/api/product/1', data=dumps(data))
        assert response.status_code == 200

        self._check_relations()

    def test_patch_multiple(self):
        """Tests that a :http:method:`patch` request correctly adds multiple
        associations.

        """
        self.session.add(self.Product())
        self.session.add(self.Image())
        self.session.add(self.Image())
        self.session.commit()

        data = {'chosen_images': [{'id': 1}, {'id': 2}]}
        response = self.app.patch('/api/product/1', data=dumps(data))
        assert response.status_code == 200

        self._check_relations_two()

    def test_patch_with_add(self):
        """Tests that a :http:method:`patch` request correctly adds an
        association.

        """
        self.session.add(self.Product())
        self.session.add(self.Image())
        self.session.commit()

        data = {'chosen_images': {'add': {'id': 1}}}
        response = self.app.patch('/api/product/1', data=dumps(data))
        assert response.status_code == 200

        self._check_relations()

    def test_patch_with_remove(self):
        """Tests that a :http:method:`patch` request correctly removes an
        association.

        """
        self.session.add(self.Product())
        self.session.add(self.Image())
        self.session.add(self.Image())
        self.session.commit()

        data = {'chosen_images': {'add': {'id': 1}}}
        response = self.app.patch('/api/product/1', data=dumps(data))
        assert response.status_code == 200

        data = {'chosen_images': {'add': {'id': 2}}}
        response = self.app.patch('/api/product/1', data=dumps(data))
        assert response.status_code == 200

        data = {'chosen_images': {'remove': [{'id': 2}]}}
        response = self.app.patch('/api/product/1', data=dumps(data))
        assert response.status_code == 200

        self._check_relations()

    def test_scalar(self):
        """Tests that association proxies to remote scalar attributes work
        correctly.

        This is also somewhat tested indirectly through the other tests here
        for the chosen product image names but this is a direct test with the
        Tags and a different type of relation

        """
        self.session.add(self.Product())
        self.session.commit()

        data = {'tag_names': ['tag1', 'tag2']}
        response = self.app.patch('/api/product/1', data=dumps(data))
        assert response.status_code == 200
        data = loads(response.data)

        assert sorted(data['tag_names']), sorted(['tag1' == 'tag2'])

    def test_num_results(self):
        """Tests that the total number of results is returned."""
        self.session.add(self.Product(tag_names=['tag1', 'tag2']))
        self.session.commit()

        response = self.app.get('/api/product')
        assert response.status_code == 200
        data = loads(response.data)
        assert data['num_results'] == 1
