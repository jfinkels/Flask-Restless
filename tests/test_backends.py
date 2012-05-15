"""
    tests.test_backends
    ~~~~~~~~~~~~~~~~~~~

    Provides unit tests for the :mod:`flask_restless.backends` module.

    :copyright: 2012 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com>
    :license: GNU AGPLv3+ or BSD

"""
from unittest2 import skipUnless
from unittest2 import TestCase
from unittest2 import TestSuite

from flask import Flask
from flask import json
try:
    from flask.ext.sqlalchemy import SQLAlchemy
except:
    has_flask_sqlalchemy = False
else:
    has_flask_sqlalchemy = True
try:
    import elixir as elx
except:
    has_elixir = False
else:
    has_elixir = True
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

from flask.ext.restless.backends import Backend
from flask.ext.restless.backends import ElixirBackend
from flask.ext.restless.backends import FlaskSQLAlchemyBackend
from flask.ext.restless.backends import FunctionEvaluationError
from flask.ext.restless.backends import infer_backend
from flask.ext.restless.backends import register_backend
from flask.ext.restless.backends import SQLAlchemyBackend
from flask.ext.restless.backends import unregister_backend

from .helpers import setUpModule
from .helpers import tearDownModule
from .helpers import TestSupportPrefilled


__all__ = ['BackendInferenceTest', 'FunctionEvaluationTest']


class BackendInferenceTest(TestCase):
    """Tests for inferring the type of database abstraction layer based on a
    given model class.

    """

    def setUp(self):
        """Creates a dummy backend class for testing."""
        class TrueBackend(Backend):
            name = 'test'
            @staticmethod
            def infer(*args, **kw):
                return True
            @staticmethod
            def query(*args, **kw):
                return 'foo'
        self.TrueBackend = TrueBackend

    def tearDown(self):
        """Unregisters the dummy backend class, in case it has been registered
        during any of the tests.

        """
        # returns None if the specified backend does not exist
        unregister_backend(self.TrueBackend)

    def test_register_backend_order(self):
        """Tests that a newly registered backend is checked in the correct
        order.

        """
        register_backend(self.TrueBackend, priority=1)
        result = infer_backend(None)
        self.assertEqual(self.TrueBackend, result)

    def test_sqlalchemy(self):
        """Tests that SQLAlchemy is correctly inferred from a SQLAlchemy model.

        """
        engine = sa.create_engine('sqlite://', convert_unicode=True)
        Base = declarative_base()
        Base.metadata.bind = engine

        class Test(Base):
            __tablename__ = 'person'
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.Unicode, unique=True)
        self.assertEqual(infer_backend(Test), SQLAlchemyBackend)
        Base.metadata.create_all()
        self.assertEqual(infer_backend(Test), SQLAlchemyBackend)
        # TODO put this in tearDown
        Base.metadata.drop_all()
        self.assertEqual(infer_backend(Test), SQLAlchemyBackend)

    def test_flask_sqlalchemy(self):
        """Tests that Flask-SQLAlchemy is correctly inferred from a
        Flask-SQLAlchemy model.

        """
        app = Flask(__name__)
        app.config['DEBUG'] = True
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        db = SQLAlchemy(app)

        class Test(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.Unicode, unique=True)
        self.assertEqual(infer_backend(Test), FlaskSQLAlchemyBackend)
        db.create_all()
        self.assertEqual(infer_backend(Test), FlaskSQLAlchemyBackend)
        # TODO put this in tearDown
        db.drop_all()
        self.assertEqual(infer_backend(Test), FlaskSQLAlchemyBackend)

    def test_elixir(self):
        """Tests that Elixir is correctly inferred from an Elixir model."""
        app = Flask(__name__)
        app.config['DEBUG'] = True
        app.config['TESTING'] = True
        elx.metadata.bind = 'sqlite://'

        class Test(elx.Entity):
            name = elx.Field(elx.Unicode, unique=True)
        self.assertEqual(infer_backend(Test), ElixirBackend)
        elx.setup_all()
        self.assertEqual(infer_backend(Test), ElixirBackend)
        elx.create_all()
        self.assertEqual(infer_backend(Test), ElixirBackend)
        # TODO put this in tearDown
        elx.drop_all()
        self.assertEqual(infer_backend(Test), ElixirBackend)

    test_flask_sqlalchemy = \
        skipUnless(has_flask_sqlalchemy,
                   'Flask-SQLAlchemy not found.')(test_flask_sqlalchemy)

    test_elixir = skipUnless(has_elixir, 'Elixir not found.')(test_elixir)


class FunctionEvaluationTest(TestSupportPrefilled):
    """Unit tests for the :func:`flask_restless.view._evaluate_functions`
    function.

    """

    def test_basic_evaluation(self):
        """Tests for basic function evaluation."""
        # test for no model
        result = SQLAlchemyBackend.evaluate_functions(self.session, None, [])
        self.assertEqual(result, {})

        # test for no functions
        result = SQLAlchemyBackend.evaluate_functions(self.Person,
                                                      self.session, [])
        self.assertEqual(result, {})

        # test for summing ages
        functions = [{'name': 'sum', 'field': 'age'}]
        result = SQLAlchemyBackend.evaluate_functions(self.Person,
                                                      self.session, functions)
        self.assertIn('sum__age', result)
        self.assertEqual(result['sum__age'], 102.0)

        # test for multiple functions
        functions = [{'name': 'sum', 'field': 'age'},
                     {'name': 'avg', 'field': 'other'}]
        result = SQLAlchemyBackend.evaluate_functions(self.Person,
                                                      self.session, functions)
        self.assertIn('sum__age', result)
        self.assertEqual(result['sum__age'], 102.0)
        self.assertIn('avg__other', result)
        self.assertEqual(result['avg__other'], 16.2)

    def test_poorly_defined_functions(self):
        """Tests that poorly defined functions raise errors."""
        # test for unknown field
        functions = [{'name': 'sum', 'field': 'bogus'}]
        with self.assertRaises(FunctionEvaluationError):
            SQLAlchemyBackend.evaluate_functions(self.Person, self.session,
                                                 functions)

        # test for unknown function
        functions = [{'name': 'bogus', 'field': 'age'}]
        with self.assertRaises(FunctionEvaluationError):
            SQLAlchemyBackend.evaluate_functions(self.Person, self.session,
                                                 functions)


def load_tests(loader, standard_tests, pattern):
    """Returns the test suite for this module."""
    suite = TestSuite()
    suite.addTest(loader.loadTestsFromTestCase(BackendInferenceTest))
    suite.addTest(loader.loadTestsFromTestCase(FunctionEvaluationTest))
    return suite
