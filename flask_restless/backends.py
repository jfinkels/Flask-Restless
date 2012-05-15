"""
    flask.ext.restless.backends
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Backend-specific helper functions.

    :copyright: 2012 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com>
    :license: GNU AGPLv3+ or BSD

    .. versionadded:: 0.6

"""
import datetime
import heapq

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.orm import object_mapper
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm.properties import RelationshipProperty as RelProperty
from sqlalchemy.sql import func
from sqlalchemy import Date
from sqlalchemy import DateTime


class FunctionEvaluationError(Exception):
    pass


class Backend(object):
    """Base class for backend-specific functionality.

    In order for Flask-Restless to provide support for specific database
    abstraction layers, it must know some backend-specific functionality. In
    order to make Flask-Restless aware, define a subclass of this class and
    implement the methods described below. In addition, each subclass must set
    the :attr:`name` attribute to be an identifying string for the backend.

    For example, a subclass which provides functionality for pure SQLAlchemy
    might look like this::

        # Step 1 - subclass Backend or SQLALchemyBackendBase (if your backend
        # is a layer on top of SQLAlchemy).
        class SQLAlchemyBackend(SQLAlchemyBackendBase):

            # Step 2 - provide an identifying string for your backend.
            name = 'sqlalchemy'

            # Step 3 - implement infer(), which is necessary for Flask-Restless
            # to guess whether a given model is defined for this particular
            # backend.
            @staticmethod
            def infer(model, *args, **kw):
                return hasattr(model, '__tablename__')

            # Step 3 - implement query(), which provides a consistent interface
            # for Flask-Restless to query a database.
            @staticmethod
            def query(model, session, *args, **kw):
                return session.query(model)

    Note that the first two parameters of both :meth:`infer` and :meth:`query`
    are ``model`` and ``session``, but you don't have to use them (as seen in
    the definition of ``infer`` in the above example). However, you should
    still provide ``*args`` and ``**kw`` parameters.

    """

    #: An identifying name for this backend.
    name = None

    @staticmethod
    def infer(model, session, *args, **kw):
        """Returns ``True`` if and only if `model` has been defined for use
        with the backend which this class represents.

        Subclasses must implement this static method, and must decorate it with
        the :func:`staticmethod` decorator.

        """
        raise NotImplementedError('Subclasses must override infer().')

    @staticmethod
    def query(model, session, *args, **kw):
        """Returns a query-like object on the specified database model.

        A "query-like object" is something like a SQLAlchemy query object. That
        means it must have at least a ``filter_by`` function.

        Subclasses must implement this static method, and must decorate it with
        the :func:`staticmethod` decorator.

        Pre-condition: `model` is not ``None``.

        """
        raise NotImplementedError('Subclasses must override query().')

    @staticmethod
    def is_date_field(model, fieldname):
        """Returns ``True`` if and only if the field of `model` with the
        specified name corresponds to either a :class:`datetime.date` object or
        a :class:`datetime.datetime` object.

        """
        raise NotImplementedError('Subclasses must override is_date_field().')

    @staticmethod
    def get_table_name(model):
        """Returns a string representing of the name of the database table
        which the specified model class represents.

        """
        raise NotImplementedError('Subclasses must override get_table_name().')

    @staticmethod
    def get_or_create(model, session, **kwargs):
        """Returns the first instance of the specified model filtered by the
        keyword arguments, or creates a new instance of the model and returns
        that.

        This function returns a two-tuple in which the first element is the
        created or retrieved instance and the second is a boolean value which
        is ``True`` if and only if an instance was created.

        The idea for this function is based on Django's
        :meth:`django.db.model.Model.get_or_create()` method.

        `session` is the session in which all database transactions are made
        (this should be something like a
        :attr:`flask.ext.sqlalchemy.SQLAlchemy.session`).

        `model` is the model to get or create (this should be something like a
        SQLAlchemy model).

        `kwargs` are the keyword arguments which will be used to match the
        instance of `model`.

        """
        raise NotImplementedError('Subclasses must override get_or_create().')

    @staticmethod
    def get_columns(model):
        """Returns a dictionary-like object containing all the columns of the
        specified `model` class.

        """
        raise NotImplementedError('Subclasses must override get_columns().')

    @staticmethod
    def get_related_model(model, relationname):
        """Gets the class of the model to which `model` is related by the
        attribute whose name is `relationname`.

        """
        raise NotImplementedError('Subclasses must override'
                                  ' get_related_model().')

    @staticmethod
    def get_relations(model):
        """Returns a list of relation names of `model` (as a list of strings).

        """
        raise NotImplementedError('Subclasses must override get_relations().')

    @staticmethod
    def to_dict(instance, deep=None, exclude=None):
        """Returns a dictionary representing the fields of the specified
        `instance` of a model.

        `deep` is a dictionary containing a mapping from a relation name (for a
        relation of `instance`) to either a list or a dictionary. This is a
        recursive structure which represents the `deep` argument when calling
        :func:`to_dict` on related instances. When an empty list is
        encountered, :func:`to_dict` returns a list of the string
        representations of the related instances.

        `exclude` specifies the columns which will *not* be present in the
        returned dictionary representation of the object.

        """
        raise NotImplementedError('Subclasses must override to_dict().')

    @staticmethod
    def evaluate_functions(model, session, functions):
        """Executes each of the functions specified in `functions`, a list of
        dictionaries of the form described below, on the given model and
        returns a dictionary mapping function name (slightly modified, see
        below) to result of evaluation of that function.

        `session` is the session in which all database transactions will be
        performed.

        `model` is the model class on which the specified functions will be
        evaluated.

        ``functions`` is a list of dictionaries of the form::

            {'name': 'avg', 'field': 'amount'}

        For example, if you want the sum and the average of the field named
        "amount"::

            >>> # assume instances of Person exist in the database...
            >>> f1 = dict(name='sum', field='amount')
            >>> f2 = dict(name='avg', field='amount')
            >>> evaluate_functions(Person, [f1, f2])
            {'avg__amount': 456, 'sum__amount': 123}

        The return value is a dictionary mapping ``'<funcname>__<fieldname>'``
        to the result of evaluating that function on that field. If `model` is
        ``None`` or `functions` is empty, this function returns the empty
        dictionary.

        Subclasses which implement this function may raise
        :exc:`FunctionEvaluationError`.

        """
        raise NotImplementedError('Subclasses must override'
                                  ' evaluate_functions().')


class SQLAlchemyBackendBase(Backend):
    """A base class for backends which are based on SQLAlchemy (including pure
    SQLAlchemy, Flask-SQLAlchemy, and Elixir).

    Use this as the base class for backends which are derived from SQLAlchemy.

    """

    @staticmethod
    def is_date_field(model, fieldname):
        prop = getattr(model, fieldname).property
        if isinstance(prop, RelationshipProperty):
            return False
        fieldtype = prop.columns[0].type
        return isinstance(fieldtype, Date) or isinstance(fieldtype, DateTime)

    @staticmethod
    def get_table_name(model):
        return model.__tablename__

    @staticmethod
    def get_or_create(model, session, **kwargs):
        # TODO document that this uses the .first() function
        instance = session.query(model).filter_by(**kwargs).first()
        if instance:
            return instance, False
        else:
            instance = model(**kwargs)
            session.add(instance)
            session.commit()
            return instance, True

    @staticmethod
    def get_columns(model):
        return model._sa_class_manager

    @staticmethod
    def get_related_model(model, relationname):
        columns = SQLAlchemyBackendBase.get_columns(model)
        return columns[relationname].property.mapper.class_

    @staticmethod
    def get_relations(model):
        cols = SQLAlchemyBackendBase.get_columns(model)
        return [k for k in cols if isinstance(cols[k].property, RelProperty)]

    # This code was adapted from :meth:`elixir.entity.Entity.to_dict` and
    # http://stackoverflow.com/q/1958219/108197.
    #
    # TODO should we have an `include` argument also?
    @staticmethod
    def to_dict(instance, deep=None, exclude=None):
        deep = deep or {}
        exclude = exclude or ()
        # create the dictionary mapping column name to value
        columns = (p.key for p in object_mapper(instance).iterate_properties
                   if isinstance(p, ColumnProperty))
        result = dict((col, getattr(instance, col)) for col in columns)
        # Convert datetime and date objects to ISO 8601 format.
        #
        # TODO We can get rid of this when issue #33 is resolved.
        for key, value in result.items():
            if isinstance(value, datetime.date):
                result[key] = value.isoformat()
        # recursively call _o_dict on each of the `deep` relations
        for relation, rdeep in deep.iteritems():
            # exclude foreign keys of the related object for the recursive call
            relationproperty = object_mapper(instance).get_property(relation)
            newexclude = (key.name for key in relationproperty.remote_side)
            # get the related value so we can see if it is None or a list
            relatedvalue = getattr(instance, relation)
            if relatedvalue is None:
                result[relation] = None
            elif isinstance(relatedvalue, list):
                result[relation] = \
                    [SQLAlchemyBackendBase.to_dict(inst, rdeep, newexclude)
                     for inst in relatedvalue]
            else:
                result[relation] = \
                    SQLAlchemyBackendBase.to_dict(relatedvalue, rdeep,
                                                  newexclude)
        return result

    @staticmethod
    def evaluate_functions(model, session, functions):
        """Evaluates functions on SQLAlchemy models.

        This function raises :exc:`FunctionEvaluationError` if a field does not
        exist on a given model or if a function does not exist. In the case of
        the former, the exception will have a ``field`` attribute which is the
        name of the field which does not exist. In the case of the latter, the
        exception will have a ``function`` attribute which is the name of the
        function with does not exist.

        """
        if not model or not functions:
            return {}
        processed = []
        funcnames = []
        for function in functions:
            funcname, fieldname = function['name'], function['field']
            # We retrieve the function by name from the SQLAlchemy ``func``
            # module and the field by name from the model class.
            #
            # If the specified field doesn't exist, this raises AttributeError.
            funcobj = getattr(func, funcname)
            try:
                field = getattr(model, fieldname)
            except AttributeError:
                message = 'No such field "%s"' % fieldname
                exception = FunctionEvaluationError(message)
                exception.field = fieldname
                raise exception
            # Time to store things to be executed. The processed list stores
            # functions that will be executed in the database and funcnames
            # contains names of the entries that will be returned to the
            # caller.
            funcnames.append('%s__%s' % (funcname, fieldname))
            processed.append(funcobj(field))
        # Evaluate all the functions at once and get an iterable of results.
        #
        # If any of the functions
        try:
            evaluated = session.query(*processed).one()
        except OperationalError, exception:
            # HACK original error message is of the form:
            #
            #    '(OperationalError) no such function: bogusfuncname'
            original_error_msg = exception.args[0]
            bad_function = original_error_msg[37:]
            message = 'No such function "%s"' % bad_function
            new_exception = FunctionEvaluationError(message)
            new_exception.function = bad_function
            raise new_exception
        return dict(zip(funcnames, evaluated))


class SQLAlchemyBackend(SQLAlchemyBackendBase):
    """Represents a pure SQLAlchemy backend."""

    name = 'sqlalchemy'

    @staticmethod
    def infer(model, *args, **kw):
        return hasattr(model, '__tablename__')

    @staticmethod
    def query(model, session, *args, **kw):
        return session.query(model)


class FlaskSQLAlchemyBackend(SQLAlchemyBackendBase):
    """Represents a Flask-SQLAlchemy backend."""

    name = 'flask-sqlalchemy'

    @staticmethod
    def infer(model, *args, **kw):
        return hasattr(model, 'query') and hasattr(model, 'query_class')

    @staticmethod
    def query(model, *args, **kw):
        return model.query


class ElixirBackend(SQLAlchemyBackendBase):
    """Represents an Elixir backend."""

    name = 'elixir'

    @staticmethod
    def get_table_name(model):
        return model.table.name

    @staticmethod
    def infer(model, *args, **kw):
        return hasattr(model, 'table')

    @staticmethod
    def query(model, *args, **kw):
        return model.query


def infer_backend(model, session=None):
    """Returns a string identifying the backend (a database abstraction layer
    like SQLAlchemy, Flask-SQLAlchemy, or Elixir) for which `model` has been
    defined.

    `session` may also be provided, though some backend inference tests will
    ignore it. `session` represents the session in which database transactions
    will be made for `model`; this may help some backend inference tests infer
    the type of backend.

    This function returns one of the backends registered in :data:`backends` or
    ``None`` if the backend could not be inferred. Note that the inference
    functions are relatively dumb---most simply check for the presence of
    attributes on the model which signify that it was defined for use with a
    particular backend.

    If this function can correctly infer the backend, it can do so regardless
    of whether the concrete tables have been created (or destroyed); that is,
    this works before your tables are created, after they are created, and
    after they have been destroyed.

    .. versionadded:: 0.6

    """
    for backend in (b for p, b in sorted(backends)):
        if backend.infer(model, session):
            return backend
    return None


def register_backend(backend, priority=None):
    """Registers `backend` with the list of known backends.

    `backend` is a subclass of :class:`Backend`.

    If `priority` is not ``None``, the backend will be added with the specified
    priority, an integer between 0 and 100 which indicates the order in which
    the backend will be tested in the :func:`infer_backend`
    function. Specifying a priority is necessary for situations in which a test
    would return ``True`` for multiple backends, and so more specific backends
    should be tested first (that is, with a higher priority). If `priority` is
    ``None``, `backend` will be added with priority higher than any other
    backend so that it is checked first.

    .. versionadded:: 0.6

    """
    if priority is None:
        # since `backends` is a heap, `backends[0]` is the minimum, i.e. the
        # highest priority
        priority = max(0, backends[0] - 1)
    heapq.heappush(backends, (priority, backend))


def unregister_backend(backend):
    """Removes `backend` from the list of known backends.

    .. versionadded:: 0.6

    """
    try:
        i = [b for p, b in backends].index(backend)
    except ValueError:
        return False
    return backends.pop(i)


#: The list of pairs of known backends with their priority when attempting to
#: infer the backend type of a model.
#:
#: Since this list is actually maintained as a heap, backends should not be
#: added directly to this list; instead, use the :func:`register_backend`
#: function to register a new backend along with its priority.
#:
#: .. versionadded:: 0.6
backends = [
    (25, ElixirBackend),
    (50, FlaskSQLAlchemyBackend),
    (75, SQLAlchemyBackend)
    ]
heapq.heapify(backends)
