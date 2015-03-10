"""
    tests.test_filtering
    ~~~~~~~~~~~~~~~~~~~~

    Provides tests for filtering resources in client requests.

    :copyright: 2015 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com> and
                contributors.
    :license: GNU AGPLv3+ or BSD

"""
try:
    from urllib.parse import quote as url_quote
except ImportError:
    from urllib import quote as url_quote
from datetime import date

from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship

from .helpers import dumps
from .helpers import loads
from .helpers import skip
from .helpers import ManagerTestBase


class TestFiltering(ManagerTestBase):
    """Tests for filtering resources."""

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask.ext.restless.manager.APIManager` for that application,
        and creates the ReSTful API endpoints for the models used in the test
        methods.

        """
        super(TestFiltering, self).setUp()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode)
            age = Column(Integer)
            birthday = Column(Date)

        class Comment(self.Base):
            __tablename__ = 'comment'
            id = Column(Integer, primary_key=True)
            content = Column(Unicode)
            author_id = Column(Integer, ForeignKey('person.id'))
            author = relationship('Person', backref=backref('comments'))

        self.Person = Person
        self.Comment = Comment
        self.Base.metadata.create_all()
        self.manager.create_api(Person)
        # HACK Need to create APIs for these other models because otherwise
        # we're not able to create the link URLs to them.
        #
        # TODO Fix this by simply not creating links to related models for
        # which no API has been made.
        self.manager.create_api(Comment)

    def search(self, url, filters=None, single=None):
        """Convenience function for performing a filtered :http:method:`get`
        request.

        `url` is the ``path`` part of the URL to which the request will be
        sent.

        If `filters` is specified, it must be a Python list containing filter
        objects. It specifies how to set the ``filter[objects]`` query
        parameter.

        If `single` is specified, it must be a Boolean. It specifies how to set
        the ``filter[single]`` query parameter.

        """
        if filters is None:
            filters = []
        target_url = '{0}?filter[objects]={1}'.format(url, dumps(filters))
        if single is not None:
            target_url += '&filter[single]={0}'.format(1 if single else 0)
        return self.app.get(target_url)

    def test_bad_filter(self):
        """Tests that providing a bad filter parameter causes an error
        response.

        """
        response = self.app.get('/api/person?filter[objects]=bogus')
        assert response.status_code == 400
        # TODO check error messages here

    def test_like(self):
        """Tests for filtering using the ``like`` operator."""
        person1 = self.Person(name='Jesus')
        person2 = self.Person(name='Mary')
        person3 = self.Person(name='Joseph')
        self.session.add_all([person1, person2, person3])
        self.session.commit()
        filters = [dict(name='name', op='like', val=url_quote('%s%'))]
        response = self.search('/api/person', filters)
        document = loads(response.data)
        people = document['data']
        assert len(people) == 2
        assert ['Jesus', 'Joseph'] == sorted(p['name'] for p in people)

    def test_single(self):
        """Tests for requiring a single resource response to a filtered
        request.

        """
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        self.session.add_all([person1, person2])
        self.session.commit()
        filters = [dict(name='id', op='equals', val='1')]
        response = self.search('/api/person', filters, single=True)
        assert response.status_code == 200
        document = loads(response.data)
        person = document['data']
        assert person['id'] == '1'

    def test_single_too_many(self):
        """Tests that requiring a single resource response returns an error if
        the filtered request would have returned more than one resource.

        """
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        self.session.add_all([person1, person2])
        self.session.commit()
        response = self.search('/api/person', single=True)
        # TODO should this be a 404? Maybe 409 is better?
        assert response.status_code == 404
        # TODO check the error message here.

    def test_single_wrong_format(self):
        """Tests that providing an incorrectly formatted argument to
        ``filter[single]`` yields an error response.

        """
        response = self.app.get('/api/person?filter[single]=bogus')
        assert response.status_code == 400
        # TODO check the error message here.

    def test_in_list(self):
        """Tests for a filter object checking for a field with value in a
        specified list of acceptable values.

        """
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        person3 = self.Person(id=3)
        self.session.add_all([person1, person2, person3])
        self.session.commit()
        filters = [dict(name='id', op='in', val=[2, 3])]
        response = self.search('/api/person', filters)
        document = loads(response.data)
        people = document['data']
        assert len(people) == 2
        assert ['2', '3'] == sorted(person['id'] for person in people)

    def test_any_in_to_many(self):
        """Test for filtering using the ``any`` operator with a sub-filter
        object on a to-many relationship.

        """
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        person3 = self.Person(id=3)
        comment1 = self.Comment(content="that's cool!", author=person1)
        comment2 = self.Comment(content='i like turtles', author=person2)
        comment3 = self.Comment(content='not cool dude', author=person3)
        self.session.add_all([person1, person2, person3])
        self.session.add_all([comment1, comment2, comment3])
        self.session.commit()
        # Search for any people who have comments that contain the word "cool".
        filters = [dict(name='comments', op='any',
                        val=dict(name='content', op='like',
                                 val=url_quote('%cool%')))]
        response = self.search('/api/person', filters)
        document = loads(response.data)
        people = document['data']
        assert len(people) == 2
        assert ['1', '3'] == sorted(person['id'] for person in people)

    def test_has_in_to_one(self):
        """Test for filtering using the ``has`` operator with a sub-filter
        object on a to-one relationship.

        """
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        person3 = self.Person(id=3)
        comment1 = self.Comment(content="that's cool!", author=person1)
        comment2 = self.Comment(content="i like turtles", author=person2)
        comment3 = self.Comment(content="not cool dude", author=person3)
        self.session.add_all([person1, person2, person3])
        self.session.add_all([comment1, comment2, comment3])
        self.session.commit()
        # Search for any comments whose author has ID equals to 1.
        filters = [dict(name='author', op='has',
                        val=dict(name='id', op='gt', val=1))]
        response = self.search('/api/comment', filters)
        document = loads(response.data)
        comments = document['data']
        assert len(comments) == 2
        assert ['2', '3'] == sorted(comment['id'] for comment in comments)

    def test_comparing_fields(self):
        """Test for comparing the value of two fields in a filter object."""
        person1 = self.Person(id=1, age=1)
        person2 = self.Person(id=2, age=3)
        person3 = self.Person(id=3, age=3)
        self.session.add_all([person1, person2, person3])
        self.session.commit()
        filters = [dict(name='age', op='eq', field='id')]
        response = self.search('/api/person', filters)
        document = loads(response.data)
        people = document['data']
        assert len(people) == 2
        assert ['1', '3'] == sorted(person['id'] for person in people)

    def test_date_yyyy_mm_dd(self):
        """Test for date parsing in filter objects with dates of the form
        ``1969-07-20``.

        """
        person1 = self.Person(id=1, birthday=date(1969, 7, 20))
        person2 = self.Person(id=2, birthday=date(1900, 1, 2))
        self.session.add_all([person1, person2])
        self.session.commit()
        filters = [dict(name='birthday', op='eq', val='1900-01-02')]
        response = self.search('/api/person', filters)
        document = loads(response.data)
        people = document['data']
        assert len(people) == 1
        assert people[0]['id'] == '2'

    def test_date_english(self):
        """Tests for date parsing in filter object with dates of the form ``2nd
        Jan 1900``.

        """
        person1 = self.Person(id=1, birthday=date(1969, 7, 20))
        person2 = self.Person(id=2, birthday=date(1900, 1, 2))
        self.session.add_all([person1, person2])
        self.session.commit()
        filters = [dict(name='birthday', op='eq', val='2nd Jan 1900')]
        response = self.search('/api/person', filters)
        document = loads(response.data)
        people = document['data']
        assert len(people) == 1
        assert people[0]['id'] == '2'

    def test_times(self):
        """Test for time parsing in filter objects."""
        assert False, 'Not implemented'

    def test_datetimes(self):
        """Test for datetime parsing in filter objects."""
        assert False, 'Not implemented'

    def test_datetime_to_date(self):
        """Tests that a filter object with a datetime value and a field with a
        ``Date`` type automatically converts the datetime to a date.

        """
        person1 = self.Person(id=1, birthday=date(1969, 7, 20))
        person2 = self.Person(id=2, birthday=date(1900, 1, 2))
        self.session.add_all([person1, person2])
        self.session.commit()
        datestring = '2nd Jan 1900 14:35'
        filters = [dict(name='birthday', op='eq', val=datestring)]
        response = self.search('/api/person', filters)
        document = loads(response.data)
        people = document['data']
        assert len(people) == 1
        assert people[0]['id'] == '2'

    def test_datetime_to_time(self):
        """Test that a datetime gets truncated to a time if the model has a
        time field.

        """
        assert False, 'Not implemented'

    def test_bad_date(self):
        """Tests that an invalid date causes an error."""
        filters = [dict(name='birthday', op='eq', val='bogus')]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check error message here

    def test_bad_time(self):
        """Tests that an invalid time causes an error."""
        filters = [dict(name='bedtime', op='eq', val='bogus')]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check error message here

    def test_bad_datetime(self):
        """Tests that an invalid datetime causes an error."""
        filters = [dict(name='created_at', op='eq', val='bogus')]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check error message here

    def test_search_boolean_formula(self):
        """Tests for Boolean formulas of filters in a search query."""
        person1 = self.Person(id=1, name='John', age=10)
        person2 = self.Person(id=2, name='Paul', age=20)
        person3 = self.Person(id=3, name='Luke', age=30)
        person4 = self.Person(id=4, name='Matthew', age=40)
        self.session.add_all([person1, person2, person3, person4])
        self.session.commit()
        # This searches for people whose name is John, or people older than age
        # 10 who have a "u" in their names. This should return three people:
        # John, Paul, and Luke.
        filters = [{'or': [{'and': [dict(name='name', op='like',
                                         val=url_quote('%u%')),
                                    dict(name='age', op='ge', val=10)]},
                           dict(name='name', op='eq', val='John')]
                    }]
        response = self.search('/api/person', filters)
        document = loads(response.data)
        people = document['data']
        assert len(people) == 3
        assert ['1', '2', '3'] == sorted(person['id'] for person in people)

    @skip("I'm not certain in what situations an invalid value should cause"
          " a SQLAlchemy error")
    def test_invalid_value(self):
        """Tests for an error response on an invalid value in a filter object.

        """
        filters = [dict(name='age', op='>', val='should not be a string')]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check the error message here

    def test_invalid_field(self):
        """Tests for an error response on an invalid field name in a filter
        object.

        """
        filters = [dict(name='foo', op='>', val=2)]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check the error message here

    def test_invalid_operator(self):
        """Tests for an error response on an invalid operator in a filter
        object.

        """
        filters = [dict(name='age', op='bogus', val=2)]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check the error message here

    def test_missing_argument(self):
        """Tests that filter requests with a missing ``'val'`` causes an error
        response.

        """
        filters = [dict(name='name', op='==')]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check error message here

    def test_missing_fieldname(self):
        """Tests that filter requests with a missing ``'name'`` causes an error
        response.

        """
        filters = [dict(op='==', val='foo')]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check error message here

    def test_missing_operator(self):
        """Tests that filter requests with a missing ``'op'`` causes an error
        response.

        """
        filters = [dict(name='age', val=3)]
        response = self.search('/api/person', filters)
        assert response.status_code == 400
        # TODO check error message here


class TestAssociationProxy(ManagerTestBase):
    """Test for filtering on association proxies."""

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask.ext.restless.manager.APIManager` for that application,
        and creates the ReSTful API endpoints for the models used in the test
        methods.

        """
        super(TestAssociationProxy, self).setUp()

        class Article(self.Base):
            __tablename__ = 'article'
            id = Column(Integer, primary_key=True)
            tags = association_proxy('articletags', 'tag',
                                     creator=lambda tag: ArticleTag(tag=tag))

        class ArticleTag(self.Base):
            __tablename__ = 'articletag'
            article_id = Column(Integer, ForeignKey('article.id'),
                                primary_key=True)
            article = relationship(Article, backref=backref('articletags'))
            tag_id = Column(Integer, ForeignKey('tag.id'), primary_key=True)
            tag = relationship('Tag')
            # extra_info = Column(Unicode)

        class Tag(self.Base):
            __tablename__ = 'tag'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode)

        self.Article = Article
        self.Tag = Tag
        self.Base.metadata.create_all()
        self.manager.create_api(Article)
        # HACK Need to create APIs for these other models because otherwise
        # we're not able to create the link URLs to them.
        #
        # TODO Fix this by simply not creating links to related models for
        # which no API has been made.
        self.manager.create_api(ArticleTag)
        self.manager.create_api(Tag)

    # TODO refactor this method
    def search(self, url, filters=None, single=None):
        """Convenience function for performing a filtered :http:method:`get`
        request.

        `url` is the ``path`` part of the URL to which the request will be
        sent.

        If `filters` is specified, it must be a Python list containing filter
        objects. It specifies how to set the ``filter[objects]`` query
        parameter.

        If `single` is specified, it must be a Boolean. It specifies how to set
        the ``filter[single]`` query parameter.

        """
        if filters is None:
            filters = []
        target_url = '{0}?filter[objects]={1}'.format(url, dumps(filters))
        if single is not None:
            target_url += '&filter[single]={0}'.format(1 if single else 0)
        return self.app.get(target_url)

    def test_any(self):
        """Tests for filtering on a many-to-many relationship via an
        association proxy backed by an association object.

        """
        article1 = self.Article(id=1)
        article2 = self.Article(id=2)
        article3 = self.Article(id=3)
        tag1 = self.Tag(name='foo')
        tag2 = self.Tag(name='bar')
        tag3 = self.Tag(name='baz')
        article1.tags = [tag1, tag2]
        article2.tags = [tag2, tag3]
        article3.tags = [tag3, tag1]
        self.session.add_all([article1, article2, article3])
        self.session.add_all([tag1, tag2, tag3])
        self.session.commit()
        filters = [dict(name='tags', op='any',
                        val=dict(name='name', op='eq', val='bar'))]
        response = self.search('/api/article', filters)
        document = loads(response.data)
        articles = document['data']
        assert ['1', '2'] == sorted(article['id'] for article in articles)


# class TestOperators(ManagerTestBase):
#     """Tests the behavior of different filter operators."""

#     def setUp(self):
#         """Creates the database, the :class:`~flask.Flask` object, the
#         :class:`~flask.ext.restless.manager.APIManager` for that application,
#         and creates the ReSTful API endpoints for the models used in the test
#         methods.

#         """
#         super(TestOperators, self).setUp()

#         class Person(self.Base):
#             __tablename__ = 'person'
#             id = Column(Integer, primary_key=True)

#         self.Person = Person
#         self.Base.metadata.create_all()
#         self.manager.create_api(Person)

#     # TODO Refactor this method out of this and the previous class.
#     def search(self, url, filters=None, single=None):
#         """Convenience function for performing a filtered :http:method:`get`
#         request.

#         `url` is the ``path`` part of the URL to which the request will be
#         sent.

#         If `filters` is specified, it must be a Python list containing filter
#         objects. It specifies how to set the ``filter[objects]`` query
#         parameter.

#         If `single` is specified, it must be a Boolean. It specifies how to set
#         the ``filter[single]`` query parameter.

#         """
#         if filters is None:
#             filters = []
#         target_url = '{0}?filter[objects]={1}'.format(url, dumps(filters))
#         if single is not None:
#             target_url += '&filter[single]={0}'.format(1 if single else 0)
#         return self.app.get(target_url)

#     def tearDown(self):
#         """Drops all tables from the temporary database."""
#         self.Base.metadata.drop_all()
