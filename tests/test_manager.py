"""
    tests.test_manager
    ~~~~~~~~~~~~~~~~~~

    Provides unit tests for the :mod:`flask_restless.manager` module.

    :copyright: 2012, 2013, 2014, 2015 Jeffrey Finkelstein
                <jeffrey.finkelstein@gmail.com> and contributors.
    :license: GNU AGPLv3+ or BSD

"""
import datetime

from flask import Flask
try:
    from flask.ext.sqlalchemy import SQLAlchemy
except ImportError:
    has_flask_sqlalchemy = False
else:
    has_flask_sqlalchemy = True
from nose.tools import raises
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode

from flask.ext.restless import APIManager
from flask.ext.restless import url_for
from flask.ext.restless import IllegalArgumentError
from flask.ext.restless.helpers import get_columns

from .helpers import DatabaseTestBase
from .helpers import ManagerTestBase
from .helpers import dumps
from .helpers import FlaskTestBase
from .helpers import force_json_contenttype
from .helpers import loads
from .helpers import skip_unless
from .helpers import unregister_fsa_session_signals


class TestLocalAPIManager(DatabaseTestBase):
    """Provides tests for :class:`flask.ext.restless.APIManager` when the tests
    require that the instance of :class:`flask.ext.restless.APIManager` has not
    yet been instantiated.

    """
    def setUp(self):
        super(TestLocalAPIManager, self).setUp()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)

        class Computer(self.Base):
            __tablename__ = 'computer'
            id = Column(Integer, primary_key=True)

        self.Person = Person
        self.Computer = Computer
        self.Base.metadata.create_all()

    def test_url_for(self):
        manager = APIManager(self.flaskapp, session=self.session)
        manager.create_api(self.Person, collection_name='people')
        manager.create_api(self.Computer, collection_name='computers')
        with self.flaskapp.app_context():
            url = url_for(self.Computer)
            assert url.endswith('/api/computers')
            assert url_for(self.Person).endswith('/api/people')
            assert url_for(self.Person, instid=1).endswith('/api/people/1')
            url = url_for(self.Person, instid=1, relationname='computers')
            assert url.endswith('/api/people/1/computers')
            url = url_for(self.Person, instid=1, relationname='computers',
                          relationinstid=2)
            assert url.endswith('/api/people/1/computers/2')

    def test_init_app(self):
        """Tests for initializing the Flask application after instantiating the
        :class:`flask.ext.restless.APIManager` object.

        """
        manager = APIManager()
        manager.init_app(self.flaskapp, session=self.session)
        manager.create_api(self.Person, app=self.flaskapp)
        response = self.app.get('/api/person')
        assert response.status_code == 200

    def test_init_app_split_initialization(self):
        manager = APIManager(session=self.session)
        manager.init_app(self.flaskapp)
        manager.create_api(self.Person, app=self.flaskapp)
        response = self.app.get('/api/person')
        assert response.status_code == 200

    def test_init_multiple(self):
        manager = APIManager(session=self.session)
        flaskapp1 = self.flaskapp
        flaskapp2 = Flask(__name__)
        testclient1 = self.app
        testclient2 = flaskapp2.test_client()
        force_json_contenttype(testclient2)
        manager.init_app(flaskapp1)
        manager.init_app(flaskapp2)
        manager.create_api(self.Person, app=flaskapp1)
        manager.create_api(self.Computer, app=flaskapp2)
        response = testclient1.get('/api/person')
        assert response.status_code == 200
        response = testclient1.get('/api/computer')
        assert response.status_code == 404
        response = testclient2.get('/api/person')
        assert response.status_code == 404
        response = testclient2.get('/api/computer')
        assert response.status_code == 200

    def test_creation_api_without_app_dependency(self):
        """Tests that api can be added before app will be passed to manager."""
        manager = APIManager()
        manager.create_api(self.Person)
        manager.init_app(self.flaskapp, self.session)
        response = self.app.get('/api/person')
        assert response.status_code == 200

    def test_multiple_app_delayed_init(self):
        manager = APIManager(session=self.session)

        # Create the Flask applications and the test clients.
        flaskapp1 = self.flaskapp
        flaskapp2 = Flask(__name__)
        testclient1 = self.app
        testclient2 = flaskapp2.test_client()
        force_json_contenttype(testclient2)

        # First create the API, then initialize the Flask applications after.
        manager.create_api(self.Person, app=flaskapp1)
        manager.create_api(self.Computer, app=flaskapp2)
        manager.init_app(flaskapp1)
        manager.init_app(flaskapp2)

        # Tests that only the first Flask application gets requests for
        # /api/person and only the second gets requests for /api/computer.
        response = testclient1.get('/api/person')
        assert response.status_code == 200
        response = testclient1.get('/api/computer')
        assert response.status_code == 404
        response = testclient2.get('/api/person')
        assert response.status_code == 404
        response = testclient2.get('/api/computer')
        assert response.status_code == 200

    def test_universal_preprocessor(self):
        """Tests universal preprocessor and postprocessor applied to all
        methods created with the API manager.

        """
        class Counter(object):
            def __init__(s):
                s.count = 0

            def increment(s):
                s.count += 1

            def __eq__(s, o):
                return s.count == o.count if isinstance(o, Counter) \
                    else s.count == o
        precount = Counter()
        postcount = Counter()

        def preget(**kw):
            precount.increment()

        def postget(**kw):
            postcount.increment()

        manager = APIManager(self.flaskapp, session=self.session,
                             preprocessors=dict(GET_MANY=[preget]),
                             postprocessors=dict(GET_MANY=[postget]))
        manager.create_api(self.Person)
        manager.create_api(self.Computer)
        self.app.get('/api/person')
        self.app.get('/api/computer')
        self.app.get('/api/person')
        assert precount == postcount == 3


class TestAPIManager(ManagerTestBase):
    """Unit tests for the :class:`flask_restless.manager.APIManager` class."""

    def setUp(self):
        super(TestAPIManager, self).setUp()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)

        class Tag(self.Base):
            __tablename__ = 'tag'
            name = Column(Unicode, primary_key=True)

        self.Person = Person
        self.Tag = Tag
        self.Base.metadata.create_all()

    def test_disallowed_methods(self):
        """Tests that disallowed methods respond with :http:status:`405`."""
        self.manager.create_api(self.Person, methods=[])
        for method in 'get', 'post', 'put', 'delete':
            func = getattr(self.app, method)
            response = func('/api/person')
            assert response.status_code == 405

    @raises(IllegalArgumentError)
    def test_missing_id(self):
        """Tests that calling :meth:`APIManager.create_api` on a model without
        an ``id`` column raises an exception.

        """
        self.manager.create_api(self.Tag)

    @raises(IllegalArgumentError)
    def test_empty_collection_name(self):
        """Tests that calling :meth:`APIManager.create_api` with an empty
        collection name raises an exception.

        """
        self.manager.create_api(self.Person, collection_name='')

    def test_disallow_functions(self):
        """Tests that if the ``allow_functions`` keyword argument is ``False``,
        no endpoint will be made available at :http:get:`/api/eval/:type`.

        """
        self.manager.create_api(self.Person, allow_functions=False)
        response = self.app.get('/api/eval/person')
        assert response.status_code == 404

    def test_include_related(self):
        """Test for specifying included columns on related models."""
        date = datetime.date(1999, 12, 31)
        person = self.Person(name=u'Test', age=10, other=20, birth_date=date)
        computer = self.Computer(name=u'foo', vendor=u'bar', buy_date=date)
        self.session.add(person)
        person.computers.append(computer)
        self.session.commit()

        include = frozenset(['name', 'age', 'computers', 'computers.id',
                             'computers.name'])
        self.manager.create_api(self.Person, include_columns=include)
        include = frozenset(['name', 'age', 'computers.id', 'computers.name'])
        self.manager.create_api(self.Person, url_prefix='/api2',
                                include_columns=include)

        response = self.app.get('/api/person/{0}'.format(person.id))
        person_dict = loads(response.data)
        for column in 'name', 'age', 'computers':
            assert column in person_dict
        for column in 'id', 'other', 'birth_date':
            assert column not in person_dict
        for column in 'id', 'name':
            assert column in person_dict['computers'][0]
        for column in 'vendor', 'owner_id', 'buy_date':
            assert column not in person_dict['computers'][0]

        response = self.app.get('/api2/person/{0}'.format(person.id))
        assert 'computers' not in loads(response.data)

    def test_include_column_attributes(self):
        """Test for specifying included columns as SQLAlchemy column attributes.

        """
        date = datetime.date(1999, 12, 31)
        person = self.Person(name=u'Test', age=10, other=20, birth_date=date)
        self.session.add(person)
        self.session.commit()

        include = frozenset([self.Person.name, self.Person.age])
        self.manager.create_api(self.Person, include_columns=include)

        response = self.app.get('/api/person/{0}'.format(person.id))
        person_dict = loads(response.data)
        for column in 'name', 'age':
            assert column in person_dict
        for column in 'id', 'other', 'birth_date':
            assert column not in person_dict

    def test_exclude_related(self):
        """Test for specifying excluded columns on related models."""
        date = datetime.date(1999, 12, 31)
        person = self.Person(name=u'Test', age=10, other=20, birth_date=date)
        computer = self.Computer(name=u'foo', vendor=u'bar', buy_date=date)
        self.session.add(person)
        person.computers.append(computer)
        self.session.commit()

        exclude = frozenset(['name', 'age', 'computers', 'computers.id',
                             'computers.name'])
        self.manager.create_api(self.Person, exclude_columns=exclude)
        exclude = frozenset(['name', 'age', 'computers.id', 'computers.name'])
        self.manager.create_api(self.Person, url_prefix='/api2',
                                exclude_columns=exclude)

        response = self.app.get('/api/person/{0}'.format(person.id))
        person_dict = loads(response.data)
        for column in 'name', 'age', 'computers':
            assert column not in person_dict
        for column in 'id', 'other', 'birth_date':
            assert column in person_dict

        response = self.app.get('/api2/person/{0}'.format(person.id))
        person_dict = loads(response.data)
        assert 'computers' in person_dict
        for column in 'id', 'name':
            assert column not in person_dict['computers'][0]
        for column in 'vendor', 'owner_id', 'buy_date':
            assert column in person_dict['computers'][0]

    def test_exclude_column_attributes(self):
        """Test for specifying excluded columns as SQLAlchemy column attributes.

        """
        date = datetime.date(1999, 12, 31)
        person = self.Person(name=u'Test', age=10, other=20, birth_date=date)
        self.session.add(person)
        self.session.commit()

        exclude = frozenset([self.Person.name, self.Person.age])
        self.manager.create_api(self.Person, exclude_columns=exclude)

        response = self.app.get('/api/person/{0}'.format(person.id))
        person_dict = loads(response.data)
        for column in 'name', 'age':
            assert column not in person_dict
        for column in 'id', 'other', 'birth_date':
            assert column in person_dict

    def test_include_columns(self):
        """Tests that the `include_columns` argument specifies which columns to
        return in the JSON representation of instances of the model.

        """
        all_columns = get_columns(self.Person)
        # allow all
        self.manager.create_api(self.Person, include_columns=None,
                                url_prefix='/all')
        self.manager.create_api(self.Person, include_columns=all_columns,
                                url_prefix='/all2')
        # allow some
        self.manager.create_api(self.Person, include_columns=('name', 'age'),
                                url_prefix='/some')
        # allow none
        self.manager.create_api(self.Person, include_columns=(),
                                url_prefix='/none')

        # create a test person
        self.manager.create_api(self.Person, methods=['POST'],
                                url_prefix='/add')
        d = dict(name=u'Test', age=10, other=20,
                 birth_date=datetime.date(1999, 12, 31).isoformat())
        response = self.app.post('/add/person', data=dumps(d))
        assert response.status_code == 201
        personid = loads(response.data)['id']

        # get all
        response = self.app.get('/all/person/{0}'.format(personid))
        for column in 'name', 'age', 'other', 'birth_date', 'computers':
            assert column in loads(response.data)
        response = self.app.get('/all2/person/{0}'.format(personid))
        for column in 'name', 'age', 'other', 'birth_date', 'computers':
            assert column in loads(response.data)

        # get some
        response = self.app.get('/some/person/{0}'.format(personid))
        for column in 'name', 'age':
            assert column in loads(response.data)
        for column in 'other', 'birth_date', 'computers':
            assert column not in loads(response.data)

        # get none
        response = self.app.get('/none/person/{0}'.format(personid))
        for column in 'name', 'age', 'other', 'birth_date', 'computers':
            assert column not in loads(response.data)

    def test_include_methods(self):
        """Tests that the `include_methods` argument specifies which methods to
        return in the JSON representation of instances of the model.

        """
        # included
        self.manager.create_api(self.Person, url_prefix='/included',
                                include_methods=['name_and_age',
                                                 'computers.speed'])
        # not included
        self.manager.create_api(self.Person, url_prefix='/not_included')
        # related object
        self.manager.create_api(self.Computer, url_prefix='/included',
                                include_methods=['owner.name_and_age'])

        # included non-callable property
        self.manager.create_api(self.Computer, url_prefix='/included_property',
                                include_methods=['speed_property'])

        # create a test person
        date = datetime.date(1999, 12, 31)
        person = self.Person(name=u'Test', age=10, other=20, birth_date=date)
        computer = self.Computer(name=u'foo', vendor=u'bar', buy_date=date)
        self.session.add(person)
        person.computers.append(computer)
        self.session.commit()

        # get one with included method
        response = self.app.get('/included/person/{0}'.format(person.id))
        assert loads(response.data)['name_and_age'] == 'Test (aged 10)'

        # get one without included method
        response = self.app.get('/not_included/person/{0}'.format(person.id))
        assert 'name_and_age' not in loads(response.data)

        # get many with included method
        response = self.app.get('/included/person')
        response_data = loads(response.data)
        assert response_data['objects'][0]['name_and_age'] == 'Test (aged 10)'

        # get one through a related object
        response = self.app.get('/included/computer')
        response_data = loads(response.data)
        assert 'name_and_age' in response_data['objects'][0]['owner']

        # get many through a related object
        response = self.app.get('/included/person')
        response_data = loads(response.data)
        assert response_data['objects'][0]['computers'][0]['speed'] == 42

        # get one with included property
        url = '/included_property/computer/{0}'.format(computer.id)
        response = self.app.get(url)
        response_data = loads(response.data)
        assert response_data['speed_property'] == 42

    def test_included_method_returns_object(self):
        """Tests that objects are serialized when returned from a method listed
        in the `include_methods` argument.

        """
        date = datetime.date(1999, 12, 31)
        person = self.Person(name=u'Test', age=10, other=20, birth_date=date)
        computer = self.Computer(name=u'foo', vendor=u'bar', buy_date=date)
        self.session.add(person)
        person.computers.append(computer)
        self.session.commit()

        self.manager.create_api(self.Person,
                                include_methods=['first_computer'])
        response = self.app.get('/api/person/1')
        assert 200 == response.status_code
        data = loads(response.data)
        assert 'first_computer' in data
        assert 'foo' == data['first_computer']['name']

    def test_exclude_columns(self):
        """Tests that the ``exclude_columns`` argument specifies which columns
        to exclude in the JSON representation of instances of the model.

        """
        all_columns = get_columns(self.Person)
        # allow all
        self.manager.create_api(self.Person, exclude_columns=None,
                                url_prefix='/all')
        self.manager.create_api(self.Person, exclude_columns=(),
                                url_prefix='/all2')
        # allow some
        exclude = ('other', 'birth_date', 'computers')
        self.manager.create_api(self.Person, exclude_columns=exclude,
                                url_prefix='/some')
        # allow none
        self.manager.create_api(self.Person, exclude_columns=all_columns,
                                url_prefix='/none')

        # create a test person
        self.manager.create_api(self.Person, methods=['POST'],
                                url_prefix='/add')
        d = dict(name=u'Test', age=10, other=20,
                 birth_date=datetime.date(1999, 12, 31).isoformat())
        response = self.app.post('/add/person', data=dumps(d))
        assert response.status_code == 201
        personid = loads(response.data)['id']

        # get all
        response = self.app.get('/all/person/{0}'.format(personid))
        for column in 'name', 'age', 'other', 'birth_date', 'computers':
            assert column in loads(response.data)
        response = self.app.get('/all2/person/{0}'.format(personid))
        for column in 'name', 'age', 'other', 'birth_date', 'computers':
            assert column in loads(response.data)

        # get some
        response = self.app.get('/some/person/{0}'.format(personid))
        for column in 'name', 'age':
            assert column in loads(response.data)
        for column in 'other', 'birth_date', 'computers':
            assert column not in loads(response.data)

        # get none
        response = self.app.get('/none/person/{0}'.format(personid))
        for column in 'name', 'age', 'other', 'birth_date', 'computers':
            assert column not in loads(response.data)

    @raises(IllegalArgumentError)
    def test_exclude_primary_key_column(self):
        """Tests that trying to create a writable API while excluding the
        primary key field raises an error.

        """
        self.manager.create_api(self.Person, exclude_columns=['id'],
                                methods=['POST'])


@skip_unless(has_flask_sqlalchemy, 'Flask-SQLAlchemy not found.')
class TestFSA(FlaskTestBase):
    """Tests which use models defined using Flask-SQLAlchemy instead of pure
    SQLAlchemy.

    """

    def setUp(self):
        """Creates the Flask application, the APIManager, the database, and the
        Flask-SQLAlchemy models.

        """
        super(TestFSA, self).setUp()
        self.db = SQLAlchemy(self.flaskapp)

        class Person(self.db.Model):
            id = self.db.Column(self.db.Integer, primary_key=True)

        self.Person = Person
        self.db.create_all()

    def tearDown(self):
        """Drops all tables from the temporary database."""
        self.db.drop_all()
        unregister_fsa_session_signals()

    def test_init_app(self):
        manager = APIManager()
        manager.init_app(self.flaskapp, flask_sqlalchemy_db=self.db)
        manager.create_api(self.Person, app=self.flaskapp)
        response = self.app.get('/api/person')
        assert response.status_code == 200

    def test_init_app_split_initialization(self):
        manager = APIManager(flask_sqlalchemy_db=self.db)
        manager.init_app(self.flaskapp)
        manager.create_api(self.Person, app=self.flaskapp)
        response = self.app.get('/api/person')
        assert response.status_code == 200
