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
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship

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

        class Article(self.Base):
            __tablename__ = 'article'
            id = Column(Integer, primary_key=True)

        self.Person = Person
        self.Article = Article
        self.Base.metadata.create_all()

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
        manager.create_api(self.Article, app=flaskapp2)
        response = testclient1.get('/api/person')
        assert response.status_code == 200
        response = testclient1.get('/api/article')
        assert response.status_code == 404
        response = testclient2.get('/api/person')
        assert response.status_code == 404
        response = testclient2.get('/api/article')
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
        manager.create_api(self.Article, app=flaskapp2)
        manager.init_app(flaskapp1)
        manager.init_app(flaskapp2)

        # Tests that only the first Flask application gets requests for
        # /api/person and only the second gets requests for /api/article.
        response = testclient1.get('/api/person')
        assert response.status_code == 200
        response = testclient1.get('/api/article')
        assert response.status_code == 404
        response = testclient2.get('/api/person')
        assert response.status_code == 404
        response = testclient2.get('/api/article')
        assert response.status_code == 200

    def test_universal_preprocessor(self):
        """Tests universal preprocessor and postprocessor applied to all
        methods created with the API manager.

        """
        counter1 = 0
        counter2 = 0

        def increment1(**kw):
            counter1 += 1

        def increment2(**kw):
            counter2 += 1

        preprocessors = dict(GET_COLLECTION=[increment1])
        postprocessors = dict(GET_COLLECTION=[increment2])
        manager = APIManager(self.flaskapp, session=self.session,
                             preprocessors=preprocessors,
                             postprocessors=postprocessors)
        manager.create_api(self.Person)
        manager.create_api(self.Article)
        self.app.get('/api/person')
        self.app.get('/api/computer')
        self.app.get('/api/person')
        assert counter1 == counter2 == 3


class TestAPIManager(ManagerTestBase):
    """Unit tests for the :class:`flask_restless.manager.APIManager` class."""

    def setUp(self):
        super(TestAPIManager, self).setUp()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode)

        class Article(self.Base):
            __tablename__ = 'article'
            id = Column(Integer, primary_key=True)
            title = Column(Unicode)
            author_id = Column(Integer, ForeignKey('person.id'))
            author = relationship(Person, backref=backref('articles'))

        class Comment(self.Base):
            __tablename__ = 'comment'
            id = Column(Integer, primary_key=True)
            article_id = Column(Integer, ForeignKey('article.id'))
            article = relationship(Article, backref=backref('comments'))

        class Tag(self.Base):
            __tablename__ = 'tag'
            name = Column(Unicode, primary_key=True)

        class Photo(self.Base):
            __tablename__ = 'photo'
            id = Column(Integer, primary_key=True)
            title = Column(Unicode)

            def website(self):
                return 'example.com'

            @property
            def year(self):
                return 2015

        self.Article = Article
        self.Person = Person
        self.Photo = Photo
        self.Tag = Tag
        self.Base.metadata.create_all()

    def test_url_for(self):
        """Tests the global :func:`flask.ext.restless.url_for` function."""
        self.manager.create_api(self.Person, collection_name='people')
        self.manager.create_api(self.Article, collection_name='articles')
        with self.flaskapp.app_context():
            url1 = url_for(self.Person)
            url2 = url_for(self.Person, instid=1)
            url3 = url_for(self.Person, instid=1, relationname='articles')
            url4 = url_for(self.Person, instid=1, relationname='articles',
                           relationinstid=2)
            assert url1.endswith('/api/people')
            assert url2.endswith('/api/people/1')
            assert url3.endswith('/api/people/1/articles')
            assert url4.endswith('/api/people/1/articles/2')

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

    def test_only_column(self):
        """Tests for specifying that responses should only include certain
        column fields.

        """
        person = self.Person(id=1, name='foo')
        self.session.add(person)
        self.session.commit()
        self.manager.create_api(self.Person, only=['name'])
        response = self.app.get('/api/person/1')
        document = loads(response.data)
        person = document['data']
        assert person['id'] == '1'
        assert person['type'] == 'person'
        assert person['name'] == 'foo'
        assert 'articles' not in person['links']

    def test_only_relationship(self):
        """Tests for specifying that response should only include certain
        relationships.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        self.manager.create_api(self.Person, only=['articles'])
        response = self.app.get('/api/person/1')
        document = loads(response.data)
        person = document['data']
        assert person['id'] == '1'
        assert person['type'] == 'person'
        assert 'name' not in person
        assert 'articles' in person['links']

    def test_only_on_included(self):
        """Tests for specifying that response should only include certain
        attributes of related models.

        """
        person = self.Person(id=1)
        article = self.Article(title='foo')
        article.author = person
        self.session.add_all([person, article])
        self.session.commit()
        only = ['articles', 'articles.title']
        self.manager.create_api(self.Person, only=only)
        response = self.app.get('/api/person/1?include=articles')
        document = loads(response.data)
        person = document['data']
        assert person['id'] == '1'
        assert person['type'] == 'person'
        assert 'name' not in person
        articles = person['links']['articles']['linkage']
        included = document['included']
        expected_ids = sorted(article['id'] for article in articles)
        actual_ids = sorted(article['id'] for article in included)
        assert expected_ids == actual_ids
        assert all('title' not in article for article in included)
        assert all('comments' in article['links'] for article in included)

    def test_only_as_objects(self):
        """Test for specifying included columns as SQLAlchemy column objects
        instead of strings.

        """
        person = self.Person(id=1, name='foo')
        self.session.add(person)
        self.session.commit()
        self.manager.create_api(self.Person, only=[self.Person.name])
        response = self.app.get('/api/person/1')
        document = loads(response.data)
        person = document['data']
        assert person['id'] == '1'
        assert person['type'] == 'person'
        assert person['name'] == 'foo'
        assert 'articles' not in person['links']

    def test_only_none(self):
        """Tests that providing an empty list as the list of fields to include
        in responses causes responses to have only the ``id`` and ``type``
        elements.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        self.manager.create_api(self.Person, only=[])
        response = self.app.get('/api/person/1')
        document = loads(response.data)
        person = document['data']
        assert all(key in ('id', 'type') for key in person)

    def test_only_callable(self):
        """Tests that callable attributes can be included using the ``only``
        keyword argument.

        """
        photo = self.Photo(id=1)
        self.session.add(photo)
        self.session.commit()
        self.manager.create_api(self.Photo, only=['website'])
        response = self.app.get('/api/photo/1')
        document = loads(response.data)
        photo = document['data']
        assert photo['id'] == '1'
        assert photo['type'] == 'photo'
        assert photo['website'] == 'example.com'
        assert 'title' not in photo
        assert 'year' not in photo

    def test_only_property(self):
        """Tests that class properties can be included using the ``only``
        keyword argument.

        """
        photo = self.Photo(id=1)
        self.session.add(photo)
        self.session.commit()
        self.manager.create_api(self.Photo, only=['year'])
        response = self.app.get('/api/photo/1')
        document = loads(response.data)
        photo = document['data']
        assert photo['id'] == '1'
        assert photo['type'] == 'photo'
        assert photo['year'] == 2015
        assert 'title' not in photo
        assert 'website' not in photo

    def test_include_methods(self):
        """Tests that the `include_methods` argument specifies which methods to
        return in the JSON representation of instances of the model.

        """
        # included
        self.manager.create_api(self.Person, url_prefix='/included',
                                include_methods=['name_and_age',
                                                 'computers.speed'])
        # related object
        self.manager.create_api(self.Computer, url_prefix='/included',
                                include_methods=['owner.name_and_age'])

        # included non-callable property
        self.manager.create_api(self.Computer, url_prefix='/included_property',
                                include_methods=['speed_property'])

        # get one through a related object
        response = self.app.get('/included/computer')
        response_data = loads(response.data)
        assert 'name_and_age' in response_data['objects'][0]['owner']

        # get many through a related object
        response = self.app.get('/included/person')
        response_data = loads(response.data)
        assert response_data['objects'][0]['computers'][0]['speed'] == 42

    # TODO Technically, a resource's attribute MAY contain any valid JSON
    # object, so this is allowed by the JSON API specification.
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
