"""
    flask.ext.restless.views
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Provides the following view classes, subclasses of
    :class:`flask.MethodView` which provide generic endpoints for interacting
    with an entity of the database:

    :class:`flask.ext.restless.views.API`
      Provides the endpoints for each of the basic HTTP methods. This is the
      main class used by the
      :meth:`flask.ext.restless.manager.APIManager.create_api` method to create
      endpoints.

    :class:`flask.ext.restless.views.FunctionAPI`
      Provides a :http:method:`get` endpoint which returns the result of
      evaluating some function on the entire collection of a given model.

    :copyright: 2011 by Lincoln de Sousa <lincoln@comum.org>
    :copyright: 2012, 2013, 2014, 2015 Jeffrey Finkelstein
                <jeffrey.finkelstein@gmail.com> and contributors.
    :license: GNU AGPLv3+ or BSD

"""
from __future__ import division

from collections import defaultdict
from functools import wraps
from itertools import chain
import math

from flask import current_app
from flask import json
from flask import jsonify as _jsonify
from flask import request
from flask.views import MethodView
from mimerender import FlaskMimeRender
from mimerender import register_mime
from sqlalchemy.exc import DataError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import ProgrammingError
# from sqlalchemy.ext.associationproxy import AssociationProxy
# from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import FlushError
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.query import Query
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import HTTPException

from .helpers import changes_on_update
from .helpers import collection_name
from .helpers import count
from .helpers import evaluate_functions
from .helpers import get_by
from .helpers import get_model
from .helpers import get_related_model
from .helpers import has_field
from .helpers import is_like_list
from .helpers import partition
from .helpers import primary_key_name
from .helpers import primary_key_value
from .helpers import session_query
from .helpers import strings_to_datetimes
from .helpers import upper_keys
from .helpers import url_for
# from .helpers import get_related_association_proxy_model
# from .search import create_query
from .search import ComparisonToNull
from .search import search
from .serialization import DeserializationException
from .serialization import SerializationException


#: Format string for creating the complete URL for a paginated response.
LINKTEMPLATE = '{0}?page[number]={1}&page[size]={2}'

#: String used internally as a dictionary key for passing header information
#: from view functions to the :func:`jsonpify` function.
_HEADERS = '__restless_headers'

#: String used internally as a dictionary key for passing status code
#: information from view functions to the :func:`jsonpify` function.
_STATUS = '__restless_status_code'

#: The Content-Type we expect for most requests to APIs.
#:
#: The JSON API specification requires the content type to be
#: ``application/vnd.api+json``.
CONTENT_TYPE = 'application/vnd.api+json'

#: SQLAlchemy errors that, when caught, trigger a rollback of the session.
ROLLBACK_ERRORS = (DataError, IntegrityError, ProgrammingError, FlushError)

# For the sake of brevity, rename this function.
chain = chain.from_iterable


class ProcessingException(HTTPException):
    """Raised when a preprocessor or postprocessor encounters a problem.

    This exception should be raised by functions supplied in the
    ``preprocessors`` and ``postprocessors`` keyword arguments to
    :class:`APIManager.create_api`. When this exception is raised, all
    preprocessing or postprocessing halts, so any processors appearing later in
    the list will not be invoked.

    `code` is the HTTP status code of the response supplied to the client in
    the case that this exception is raised. `description` is an error message
    describing the cause of this exception. This message will appear in the
    JSON object in the body of the response to the client.

    """
    def __init__(self, description='', code=400, *args, **kwargs):
        super(ProcessingException, self).__init__(*args, **kwargs)
        self.code = code
        self.description = description


def _is_msie8or9():
    """Returns ``True`` if and only if the user agent of the client making the
    request indicates that it is Microsoft Internet Explorer 8 or 9.

    .. note::

       We have no way of knowing if the user agent is lying, so we just make
       our best guess based on the information provided.

    """
    # request.user_agent.version comes as a string, so we have to parse it
    version = lambda ua: tuple(int(d) for d in ua.version.split('.'))
    return (request.user_agent is not None
            and request.user_agent.version is not None
            and request.user_agent.browser == 'msie'
            and (8, 0) <= version(request.user_agent) < (10, 0))


def catch_processing_exceptions(func):
    """Decorator that catches :exc:`ProcessingException`s and subsequently
    returns a JSON-ified error response.

    """
    @wraps(func)
    def new_func(*args, **kw):
        try:
            return func(*args, **kw)
        except ProcessingException as exception:
            current_app.logger.exception(str(exception))
            detail = exception.description or str(exception)
            return error_response(exception.code, detail=detail)
    return new_func


def requires_json_api_accept(func):
    @wraps(func)
    def new_func(*args, **kw):
        if request.headers.get('Accept') != CONTENT_TYPE:
            detail = ('Request must have "Accept: {0}"'
                      ' header'.format(CONTENT_TYPE))
            return error_response(406, detail=detail)
        return func(*args, **kw)
    return new_func


def requires_json_api_mimetype(func):
    @wraps(func)
    def new_func(*args, **kw):
        content_type = request.headers.get('Content-Type')
        content_is_json = content_type.startswith(CONTENT_TYPE)
        is_msie = _is_msie8or9()
        # Request must have the Content-Type: application/vnd.api+json header,
        # unless the User-Agent string indicates that the client is Microsoft
        # Internet Explorer 8 or 9 (which has a fixed Content-Type of
        # 'text/html'; for more information, see issue #267).
        if not is_msie and not content_is_json:
            detail = ('Request must have "Content-Type: {0}"'
                      ' header').format(CONTENT_TYPE)
            return error_response(415, detail=detail)
        return func(*args, **kw)
    return new_func


def catch_integrity_errors(session):
    """Returns a decorator that catches database integrity errors.

    `session` is the SQLAlchemy session in which all database transactions will
    be performed.

    View methods can be wrapped like this::

        @catch_integrity_errors(session)
        def get(self, *args, **kw):
            return '...'

    Specifically, functions wrapped with the returned decorator catch
    :exc:`IntegrityError`s, :exc:`DataError`s, and
    :exc:`ProgrammingError`s. After the exceptions are caught, the session is
    rolled back, the exception is logged on the current Flask application, and
    an error response is returned to the client.

    """
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kw):
            try:
                return func(*args, **kw)
            # TODO should `sqlalchemy.exc.InvalidRequestError`s also be caught?
            except ROLLBACK_ERRORS as exception:
                session.rollback()
                current_app.logger.exception(str(exception))
                # Special status code for conflicting instances: 409 Conflict
                status = 409 if is_conflict(exception) else 400
                return dict(message=type(exception).__name__), status
        return wrapped
    return decorator


def is_conflict(exception):
    """Returns ``True`` if and only if the specified exception represents a
    conflict in the database.

    """
    string = str(exception)
    return 'conflicts with' in string or 'UNIQUE constraint failed' in string


def set_headers(response, headers):
    """Sets the specified headers on the specified response.

    `response` is a Flask response object, and `headers` is a dictionary of
    headers to set on the specified response. Any existing headers that
    conflict with `headers` will be overwritten.

    """
    for key, value in headers.items():
        response.headers.set(key, value)


def jsonify(*args, **kw):
    """Same as :func:`flask.jsonify`, but sets response headers.

    If ``headers`` is a keyword argument, this function will construct the JSON
    response via :func:`flask.jsonify`, then set the specified ``headers`` on
    the response. ``headers`` must be a dictionary mapping strings to strings.

    """
    response = _jsonify(*args, **kw)
    if 'headers' in kw:
        set_headers(response, kw['headers'])
    return response


# This code is (lightly) adapted from the ``requests`` library, in the
# ``requests.utils`` module. See <http://python-requests.org> for more
# information.
def _link_to_json(value):
    """Returns a list representation of the specified HTTP Link header
    information.

    `value` is a string containing the link header information. If the link
    header information (the part of after ``Link:``) looked like this::

        <url1>; rel="next", <url2>; rel="foo"; bar="baz"

    then this function returns a list that looks like this::

        [{"url": "url1", "rel": "next"},
         {"url": "url2", "rel": "foo", "bar": "baz"}]

    This example is adapted from the documentation of GitHub's API.

    """
    links = []
    replace_chars = " '\""
    for val in value.split(","):
        try:
            url, params = val.split(";", 1)
        except ValueError:
            url, params = val, ''
        link = {}
        link["url"] = url.strip("<> '\"")
        for param in params.split(";"):
            try:
                key, value = param.split("=")
            except ValueError:
                break
            link[key.strip(replace_chars)] = value.strip(replace_chars)
        links.append(link)
    return links


def _headers_to_json(headers):
    """Returns a dictionary representation of the specified dictionary of HTTP
    headers ready for use as a JSON object.

    Pre-condition: headers is not ``None``.

    """
    link = headers.pop('Link', None)
    # Shallow copy is fine here because the `headers` dictionary maps strings
    # to strings to strings.
    result = headers.copy()
    if link:
        result['Link'] = _link_to_json(link)
    return result


def jsonpify(*args, **kw):
    """Passes the specified arguments directly to :func:`jsonify` with a status
    code of 200, then wraps the response with the name of a JSON-P callback
    function specified as a query parameter called ``'callback'`` (or does
    nothing if no such callback function is specified in the request).

    If the keyword arguments include the string specified by :data:`_HEADERS`,
    its value must be a dictionary specifying headers to set before sending the
    JSONified response to the client. Headers on the response will be
    overwritten by headers specified in this dictionary.

    If the keyword arguments include the string specified by :data:`_STATUS`,
    its value must be an integer representing the status code of the response.
    Otherwise, the status code of the response will be :http:status:`200`.

    """
    # HACK In order to make the headers and status code available in the
    # content of the response, we need to send it from the view function to
    # this jsonpify function via its keyword arguments. This is a limitation of
    # the mimerender library: it has no way of making the headers and status
    # code known to the rendering functions.
    headers = kw.pop(_HEADERS, {})
    status_code = kw.pop(_STATUS, 200)
    response = jsonify(*args, **kw)
    callback = request.args.get('callback', False)
    if callback:
        # Reload the data from the constructed JSON string so we can wrap it in
        # a JSONP function.
        document = json.loads(response.data)
        # Force the 'Content-Type' header to be 'application/javascript'.
        #
        # Note that this is different from the mimetype used in Flask for JSON
        # responses; Flask uses 'application/json'. We use
        # 'application/javascript' because a JSONP response is valid
        # Javascript, but not valid JSON (and not a valid JSON API document).
        mimetype = 'application/javascript'
        headers['Content-Type'] = mimetype
        # Add the headers and status code as metadata to the JSONP response.
        meta = _headers_to_json(headers) if headers is not None else {}
        meta['status'] = status_code
        if 'meta' in document:
            document['meta'].update(meta)
        else:
            document['meta'] = meta
        inner = json.dumps(document)
        content = '{0}({1})'.format(callback, inner)
        # Note that this is different from the mimetype used in Flask for JSON
        # responses; Flask uses 'application/json'. We use
        # 'application/javascript' because a JSONP response is not valid JSON.
        response = current_app.response_class(content, mimetype=mimetype)
    if 'Content-Type' not in headers:
        headers['Content-Type'] = CONTENT_TYPE
    # Set the headers on the HTTP response as well.
    if headers:
        set_headers(response, headers)
    response.status_code = status_code
    return response


def _parse_includes(column_names):
    """Returns a pair, consisting of a list of column names to include on the
    left and a dictionary mapping relation name to a list containing the names
    of fields on the related model which should be included.

    `column_names` must be a list of strings.

    If the name of a relation appears as a key in the dictionary, then it will
    not appear in the list.

    """
    dotted_names, columns = partition(column_names, lambda name: '.' in name)
    # Create a dictionary mapping relation names to fields on the related
    # model.
    relations = defaultdict(list)
    for name in dotted_names:
        relation, field = name.split('.', 1)
        # Only add the relation if it's column has been specified.
        if relation in columns:
            relations[relation].append(field)
    # Included relations need only be in the relations dictionary, not the
    # columns list.
    for relation in relations:
        if relation in columns:
            columns.remove(relation)
    return columns, relations


def parse_sparse_fields(type_=None):
    # TODO use a regular expression to ensure field parameters are of the
    # correct format? (maybe ``field\[[^\[\]\.]*\]``)
    fields = {key[7:-1]: set(value.split(','))
              for key, value in request.args.items()
              if key.startswith('fields[') and key.endswith(']')}
    return fields.get(type_) if type_ is not None else fields


def _parse_excludes(column_names):
    """Returns a pair, consisting of a list of column names to exclude on the
    left and a dictionary mapping relation name to a list containing the names
    of fields on the related model which should be excluded.

    `column_names` must be a list of strings.

    If the name of a relation appears in the list then it will not appear in
    the dictionary.

    """
    dotted_names, columns = partition(column_names, lambda name: '.' in name)
    # Create a dictionary mapping relation names to fields on the related
    # model.
    relations = defaultdict(list)
    for name in dotted_names:
        relation, field = name.split('.', 1)
        # Only add the relation if it's column has not been specified.
        if relation not in columns:
            relations[relation].append(field)
    # Relations which are to be excluded entirely need only be in the columns
    # list, not the relations dictionary.
    for column in columns:
        if column in relations:
            del relations[column]
    return columns, relations


# TODO these need to become JSON Pointers
def extract_error_messages(exception):
    """Tries to extract a dictionary mapping field name to validation error
    messages from `exception`, which is a validation exception as provided in
    the ``validation_exceptions`` keyword argument in the constructor of this
    class.

    Since the type of the exception is provided by the user in the constructor
    of this class, we don't know for sure where the validation error messages
    live inside `exception`. Therefore this method simply attempts to access a
    few likely attributes and returns the first one it finds (or ``None`` if no
    error messages dictionary can be extracted).

    """
    # Check for our own built-in validation error.
    if isinstance(exception, DeserializationException):
        return exception.args[0]
    # 'errors' comes from sqlalchemy_elixir_validations
    if hasattr(exception, 'errors'):
        return exception.errors
    # 'message' comes from savalidation
    if hasattr(exception, 'message'):
        # TODO this works only if there is one validation error
        try:
            left, right = str(exception).rsplit(':', 1)
            left_bracket = left.rindex('[')
            right_bracket = right.rindex(']')
        except ValueError as exc:
            current_app.logger.exception(str(exc))
            # could not parse the string; we're not trying too hard here...
            return None
        msg = right[:right_bracket].strip(' "')
        fieldname = left[left_bracket + 1:].strip()
        return {fieldname: msg}
    return None


def error(id=None, href=None, status=None, code=None, title=None,
          detail=None, links=None, paths=None):
    # HACK We use locals() so we don't have to list every keyword argument.
    if all(kwvalue is None for kwvalue in locals().values()):
        raise ValueError('At least one of the arguments must not be None.')
    return dict(id=id, href=href, status=status, code=code, title=title,
                detail=detail, links=links, paths=paths)


def error_response(status, **kw):
    """Returns a correctly formatted error response with the specified
    parameters.

    This is a convenience function for::

        errors_response(status, [error(**kw)])

    For more information, see :func:`errors_response`.

    """
    return errors_response(status, [error(**kw)])


def errors_response(status, errors):
    """Return an error response with multiple errors.

    `status` is an integer representing an HTTP status code corresponding to an
    error response.

    `errors` is a list of error dictionaries, each of which must satisfy the
    requirements of the JSON API specification.

    This function returns a two-tuple whose left element is a dictionary
    containing the errors under the top-level key ``errors`` and whose right
    element is `status`.

    The returned dictionary object also includes a key with a special name,
    stored in the key :data:`_STATUS`, which is used to workaround an
    incompatibility between Flask and mimerender that doesn't allow setting
    headers on a global response object.

    The keys within each error object are described in the `Errors`_ section of
    the JSON API specification.

    .. _Errors: http://jsonapi.org/format/#errors

    """
    return {'errors': errors, _STATUS: status}, status


# Register the JSON API content type so that mimerender knows to look for it.
register_mime('jsonapi', (CONTENT_TYPE, ))

#: Creates the mimerender object necessary for decorating responses with a
#: function that automatically formats the dictionary in the appropriate format
#: based on the ``Accept`` header.
#:
#: Technical details: the first pair of parantheses instantiates the
#: :class:`mimerender.FlaskMimeRender` class. The second pair of parentheses
#: creates the decorator, so that we can simply use the variable ``mimerender``
#: as a decorator.
# TODO fill in xml renderer
mimerender = FlaskMimeRender()(default='jsonapi', jsonapi=jsonpify)


class ModelView(MethodView):
    """Base class for :class:`flask.MethodView` classes which represent a view
    of a SQLAlchemy model.

    The model class for this view can be accessed from the :attr:`model`
    attribute, and the session in which all database transactions will be
    performed when dealing with this model can be accessed from the
    :attr:`session` attribute.

    When subclasses wish to make queries to the database model specified in the
    constructor, they should access the ``self.query`` function, which
    delegates to the appropriate SQLAlchemy query object or Flask-SQLAlchemy
    query object, depending on how the model has been defined.

    """

    #: List of decorators applied to every method of this class.
    #:
    #: If a subclass must add more decorators, prepend them to this list::
    #:
    #:     class MyView(ModelView):
    #:         decorators = [my_decorator] + ModelView.decorators
    #:
    #: This way, the :data:`mimerender` function appears last. It must appear
    #: last so that it can render the returned dictionary.
    decorators = [requires_json_api_accept, requires_json_api_mimetype,
                  mimerender]

    def __init__(self, session, model, *args, **kw):
        """Calls the constructor of the superclass and specifies the model for
        which this class provides a ReSTful API.

        `session` is the SQLAlchemy session in which all database transactions
        will be performed.

        `model` is the SQLALchemy declarative model class of the database model
        for which this instance of the class is an API.

        """
        super(ModelView, self).__init__(*args, **kw)
        self.session = session
        self.model = model

    def query(self, model=None):
        """Returns either a SQLAlchemy query or Flask-SQLAlchemy query object
        (depending on the type of the model) on the specified `model`, or if
        `model` is ``None``, the model specified in the constructor of this
        class.

        """
        return session_query(self.session, model or self.model)


class FunctionAPI(ModelView):
    """Provides method-based dispatching for :http:method:`get` requests which
    wish to apply SQL functions to all instances of a model.

    .. versionadded:: 0.4

    """

    def get(self):
        """Returns the result of evaluating the SQL functions specified in the
        body of the request.

        For a description of the request and response formats, see
        :ref:`functionevaluation`.

        """
        if 'functions' not in request.args:
            detail = 'Must provide `functions` query parameter'
            return error_response(400, detail=detail)
        functions = request.args.get('functions')
        if functions is None:
            detail = '`functions` query parameter must not be empty'
            return error_response(400, detail=detail)
        try:
            data = json.loads(str(functions)) or []
        except (TypeError, ValueError, OverflowError) as exception:
            current_app.logger.exception(str(exception))
            detail = 'Unable to decode JSON in `functions` query parameter'
            return error_response(400, detail=detail)
        try:
            result = evaluate_functions(self.session, self.model, data)
            return dict(data=result)
        except AttributeError as exception:
            current_app.logger.exception(str(exception))
            detail = 'No such field "{0}"'.format(exception.field)
            return error_response(400, detail=detail)
        except KeyError as exception:
            current_app.logger.exception(str(exception))
            return error_response(400, detail=str(exception))
        except OperationalError as exception:
            current_app.logger.exception(str(exception))
            detail = 'No such function "{0}"'.format(exception.function)
            return error_response(400, detail=detail)


class APIBase(ModelView):

    #: List of decorators applied to every method of this class.
    decorators = [catch_processing_exceptions] + ModelView.decorators

    def __init__(self, session, model, preprocessors=None, postprocessors=None,
                 primary_key=None, validation_exceptions=None,
                 allow_to_many_replacement=None, *args, **kw):
        super(APIBase, self).__init__(session, model, *args, **kw)
        self.allow_to_many_replacement = allow_to_many_replacement
        self.validation_exceptions = tuple(validation_exceptions or ())
        self.primary_key = primary_key
        self.postprocessors = defaultdict(list)
        self.preprocessors = defaultdict(list)
        self.postprocessors.update(upper_keys(postprocessors or {}))
        self.preprocessors.update(upper_keys(preprocessors or {}))

        # HACK: We would like to use the :attr:`API.decorators` class attribute
        # in order to decorate each view method with a decorator that catches
        # database integrity errors. However, in order to rollback the session,
        # we need to have a session object available to roll back. Therefore we
        # need to manually decorate each of the view functions here.
        decorate = lambda name, f: setattr(self, name, f(getattr(self, name)))
        for method in ['get', 'post', 'patch', 'put', 'delete']:
            # Check if the subclass has the method before trying to decorate
            # it.
            if hasattr(self, method):
                decorate(method, catch_integrity_errors(self.session))

    def _handle_validation_exception(self, exception):
        """Rolls back the session, extracts validation error messages, and
        returns a :func:`flask.jsonify` response with :http:statuscode:`400`
        containing the extracted validation error messages.

        Again, *this method calls
        :meth:`sqlalchemy.orm.session.Session.rollback`*.

        """
        self.session.rollback()
        errors = extract_error_messages(exception)
        if not errors:
            return error_response(400, title='Validation error')
        if isinstance(errors, dict):
            errors = [error(title='Validation error',
                            detail='{0}: {1}'.format(field, detail))
                      for field, detail in errors.items()]
        return errors_response(400, errors)


class API(APIBase):
    """Provides method-based dispatching for :http:method:`get`,
    :http:method:`post`, :http:method:`patch`, :http:method:`put`, and
    :http:method:`delete` requests, for both collections of models and
    individual models.

    """

    def __init__(self, session, model, page_size=10, max_page_size=100,
                 serializer=None, deserializer=None, includes=None,
                 allow_client_generated_ids=False, allow_delete_many=False,
                 *args, **kw):
        """Instantiates this view with the specified attributes.

        `session` is the SQLAlchemy session in which all database transactions
        will be performed.

        `model` is the SQLAlchemy model class for which this instance of the
        class is an API. This model should live in `database`.

        `collection_name` is a string by which a collection of instances of
        `model` are presented to the user.

        `validation_exceptions` is the tuple of exceptions raised by backend
        validation (if any exist). If exceptions are specified here, any
        exceptions which are caught when writing to the database. Will be
        returned to the client as a :http:statuscode:`400` response with a
        message specifying the validation error which occurred. For more
        information, see :ref:`validation`.

        If either `include_columns` or `exclude_columns` is not ``None``,
        exactly one of them must be specified. If both are not ``None``, then
        the behavior of this function is undefined. `exclude_columns` must be
        an iterable of strings specifying the columns of `model` which will
        *not* be present in the JSON representation of the model provided in
        response to :http:method:`get` requests.  Similarly, `include_columns`
        specifies the *only* columns which will be present in the returned
        dictionary. In other words, `exclude_columns` is a blacklist and
        `include_columns` is a whitelist; you can only use one of them per API
        endpoint. If either `include_columns` or `exclude_columns` contains a
        string which does not name a column in `model`, it will be ignored.

        If `include_columns` is an iterable of length zero (like the empty
        tuple or the empty list), then the returned dictionary will be
        empty. If `include_columns` is ``None``, then the returned dictionary
        will include all columns not excluded by `exclude_columns`.

        If `include_methods` is an iterable of strings, the methods with names
        corresponding to those in this list will be called and their output
        included in the response.

        See :ref:`includes` for information on specifying included or excluded
        columns on fields of related models.

        `results_per_page` is a positive integer which represents the default
        number of results which are returned per page. Requests made by clients
        may override this default by specifying ``results_per_page`` as a query
        argument. `max_results_per_page` is a positive integer which represents
        the maximum number of results which are returned per page. This is a
        "hard" upper bound in the sense that even if a client specifies that
        greater than `max_results_per_page` should be returned, only
        `max_results_per_page` results will be returned. For more information,
        see :ref:`serverpagination`.

        .. deprecated:: 0.9.2
           The `post_form_preprocessor` keyword argument is deprecated in
           version 0.9.2. It will be removed in version 1.0. Replace code that
           looks like this::

               manager.create_api(Person, post_form_preprocessor=foo)

           with code that looks like this::

               manager.create_api(Person, preprocessors=dict(POST=[foo]))

           See :ref:`processors` for more information and examples.

        `post_form_preprocessor` is a callback function which takes
        POST input parameters loaded from JSON and enhances them with other
        key/value pairs. The example use of this is when your ``model``
        requires to store user identity and for security reasons the identity
        is not read from the post parameters (where malicious user can tamper
        with them) but from the session.

        `preprocessors` is a dictionary mapping strings to lists of
        functions. Each key is the name of an HTTP method (for example,
        ``'GET'`` or ``'POST'``). Each value is a list of functions, each of
        which will be called before any other code is executed when this API
        receives the corresponding HTTP request. The functions will be called
        in the order given here. The `postprocessors` keyword argument is
        essentially the same, except the given functions are called after all
        other code. For more information on preprocessors and postprocessors,
        see :ref:`processors`.

        `primary_key` is a string specifying the name of the column of `model`
        to use as the primary key for the purposes of creating URLs. If the
        `model` has exactly one primary key, there is no need to provide a
        value for this. If `model` has two or more primary keys, you must
        specify which one to use.

        `serializer` and `deserializer` are custom serialization functions. The
        former function must take a single argument representing the instance
        of the model to serialize, and must return a dictionary representation
        of that instance. The latter function must take a single argument
        representing the dictionary representation of an instance of the model
        and must return an instance of `model` that has those attributes. For
        more information, see :ref:`serialization`.

        .. versionadded:: 0.17.0
           Added the `serializer` and `deserializer` keyword arguments.

        .. versionadded:: 0.13.0
           Added the `primary_key` keyword argument.

        .. versionadded:: 0.10.2
           Added the `include_methods` keyword argument.

        .. versionchanged:: 0.10.0
           Removed `authentication_required_for` and `authentication_function`
           keyword arguments.

           Use the `preprocesors` and `postprocessors` keyword arguments
           instead. For more information, see :ref:`authentication`.

        .. versionadded:: 0.9.2
           Added the `preprocessors` and `postprocessors` keyword arguments.

        .. versionadded:: 0.9.0
           Added the `max_results_per_page` keyword argument.

        .. versionadded:: 0.7
           Added the `exclude_columns` keyword argument.

        .. versionadded:: 0.6
           Added the `results_per_page` keyword argument.

        .. versionadded:: 0.5
           Added the `include_columns`, and `validation_exceptions` keyword
           arguments.

        .. versionadded:: 0.4
           Added the `authentication_required_for` and
           `authentication_function` keyword arguments.

        """
        super(API, self).__init__(session, model, *args, **kw)
        self.default_includes = includes
        if self.default_includes is not None:
            self.default_includes = frozenset(self.default_includes)
        self.collection_name = collection_name(self.model)
        self.page_size = page_size
        self.max_page_size = max_page_size
        self.allow_client_generated_ids = allow_client_generated_ids
        self.allow_delete_many = allow_delete_many
        # Use our default serializer and deserializer if none are specified.
        if serializer is None:
            self.serialize = self._inst_to_dict
        else:
            self.serialize = serializer
        if deserializer is None:
            self.deserialize = self._dict_to_inst
            # # And check for our own default ValidationErrors here
            # self.validation_exceptions = tuple(list(self.validation_exceptions)
            #                                    + [ValidationError])
        else:
            self.deserialize = deserializer

    def _search(self):
        """Defines a generic search function for the database model.

        If the query string is empty, or if the specified query is invalid for
        some reason (for example, searching for all person instances with), the
        response will be the JSON string ``{"objects": []}``.

        To search for entities meeting some criteria, the client makes a
        request to :http:get:`/api/<modelname>` with a query string containing
        the parameters of the search. The parameters of the search can involve
        filters. In a filter, the client specifies the name of the field by
        which to filter, the operation to perform on the field, and the value
        which is the argument to that operation. In a function, the client
        specifies the name of a SQL function which is executed on the search
        results; the result of executing the function is returned to the
        client.

        The parameters of the search must be provided in JSON form as the value
        of the ``q`` request query parameter. For example, in a database of
        people, to search for all people with a name containing a "y", the
        client would make a :http:method:`get` request to ``/api/person`` with
        query parameter as follows::

            q={"filters": [{"name": "name", "op": "like", "val": "%y%"}]}

        If multiple objects meet the criteria of the search, the response has
        :http:status:`200` and content of the form::

        .. sourcecode:: javascript

           {"objects": [{"name": "Mary"}, {"name": "Byron"}, ...]}

        If the result of the search is a single instance of the model, the JSON
        representation of that instance would be the top-level object in the
        content of the response::

        .. sourcecode:: javascript

           {"name": "Mary", ...}

        For more information SQLAlchemy operators for use in filters, see the
        `SQLAlchemy SQL expression tutorial
        <http://docs.sqlalchemy.org/en/latest/core/tutorial.html>`_.

        The general structure of request data as a JSON string is as follows::

        .. sourcecode:: javascript

           {
             "single": true,
             "order_by": [{"field": "age", "direction": "asc"}],
             "limit": 2,
             "offset": 1,
             "disjunction": true,
             "filters":
               [
                 {"name": "name", "val": "%y%", "op": "like"},
                 {"name": "age", "val": [18, 19, 20, 21], "op": "in"},
                 {"name": "age", "op": "gt", "field": "height"},
                 ...
               ]
           }

        For a complete description of all possible search parameters and
        responses, see :ref:`searchformat`.

        """
        # Determine filtering options.
        try:
            filters = json.loads(request.args.get('filter[objects]', '[]'))
        except (TypeError, ValueError, OverflowError) as exception:
            current_app.logger.exception(str(exception))
            detail = 'Unable to decode filter objects as JSON list'
            return error_response(400, detail=detail)
        # TODO fix this using the below
        #filters = [strings_to_dates(self.model, f) for f in filters]

        # # resolve date-strings as required by the model
        # for param in search_params.get('filters', list()):
        #     if 'name' in param and 'val' in param:
        #         query_model = self.model
        #         query_field = param['name']
        #         if '__' in param['name']:
        #             fieldname, relation = param['name'].split('__')
        #             submodel = getattr(self.model, fieldname)
        #             if isinstance(submodel, InstrumentedAttribute):
        #                 query_model = submodel.property.mapper.class_
        #                 query_field = relation
        #             elif isinstance(submodel, AssociationProxy):
        #                 # For the sake of brevity, rename this function.
        #                 get_assoc = get_related_association_proxy_model
        #                 query_model = get_assoc(submodel)
        #                 query_field = relation
        #         to_convert = {query_field: param['val']}
        #         try:
        #             result = strings_to_dates(query_model, to_convert)
        #         except ValueError as exception:
        #             current_app.logger.exception(str(exception))
        #             return dict(message='Unable to construct query'), 400
        #         param['val'] = result.get(query_field)

        # Determine sorting options.
        sort = request.args.get('sort')
        if sort:
            sort = [(value[0], value[1:]) for value in sort.split(',')]
        else:
            sort = []
        if any(order not in ('+', '-') for order, field in sort):
            detail = 'Each sort parameter must begin with "+" or "-".'
            return error_response(400, detail=detail)

        # Determine grouping options.
        group_by = request.args.get('group')
        if group_by:
            group_by = group_by.split(',')
        else:
            group_by = []

        # Determine whether the client expects a single resource response.
        try:
            single = bool(int(request.args.get('filter[single]', 0)))
        except ValueError as exception:
            current_app.logger.exception(str(exception))
            detail = 'Invalid format for filter[single] query parameter'
            return error_response(400, detail=detail)

        for preprocessor in self.preprocessors['GET_COLLECTION']:
            preprocessor(filters=filters, sort=sort, single=single)

        # Compute the result of the search on the model.
        try:
            result = search(self.session, self.model, filters=filters,
                            sort=sort, group_by=group_by, single=single)
        except NoResultFound:
            return error_response(404, detail='No result found')
        except MultipleResultsFound:
            return error_response(404, detail='Multiple results found')
        except ComparisonToNull as exception:
            detail = str(exception)
            return error_response(400, detail=detail)
        except Exception as exception:
            current_app.logger.exception(str(exception))
            return error_response(400, detail='Unable to construct query')

        # # create a placeholder for the relations of the returned models
        # relations = frozenset(get_relations(self.model))
        # # do not follow relations that will not be included in the response
        # if self.include_columns is not None:
        #     cols = frozenset(self.include_columns)
        #     rels = frozenset(self.include_relations)
        #     relations &= (cols | rels)
        # elif self.exclude_columns is not None:
        #     relations -= frozenset(self.exclude_columns)
        # deep = dict((r, {}) for r in relations)

        # Determine the client's request for which fields to include for this
        # type of object.
        fields = parse_sparse_fields(self.collection_name)
        # if self.collection_name in fields and self.default_fields is not None:
        #     fields[self.collection_name] |= self.default_fields
        #fields = fields.get(self.collection_name)

        # If the result of the search is a SQLAlchemy query object, we need to
        # return a collection.
        pagination_links = dict()
        if isinstance(result, Query):
            # Determine the client's pagination request: page size and number.
            page_size = int(request.args.get('page[size]', self.page_size))
            if page_size < 0:
                detail = 'Page size must be a positive integer'
                return error_response(400, detail=detail)
            if page_size > self.max_page_size:
                detail = "Page size must not exceed the server's maximum: {0}"
                detail = detail.format(self.max_page_size)
                return error_response(400, detail=detail)
            # If the page size is 0, just return everything.
            if page_size == 0:
                num_results = count(self.session, result)
                headers = dict()
                result = [self.serialize(instance, only=fields)
                          for instance in result]
            # Otherwise, the page size is greater than zero, so paginate the
            # response.
            else:
                page_number = int(request.args.get('page[number]', 1))
                if page_number < 0:
                    detail = 'Page number must be a positive integer'
                    return error_response(400, detail=detail)
                # If the query is really a Flask-SQLAlchemy query, we can use
                # its built-in pagination.
                if hasattr(result, 'paginate'):
                    pagination = result.paginate(page_number, page_size,
                                                 error_out=False)
                    num_results = pagination.total
                    first = 1
                    last = pagination.pages
                    prev = pagination.prev_num
                    next_ = pagination.next_num
                    result = [self.serialize(instance, only=fields)
                              for instance in pagination.items]
                else:
                    num_results = count(self.session, result)
                    first = 1
                    # There will be no division-by-zero error here because we
                    # have already checked that page size is not equal to zero
                    # above.
                    last = int(math.ceil(num_results / page_size))
                    prev = page_number - 1 if page_number > 1 else None
                    next_ = page_number + 1 if page_number < last else None
                    offset = (page_number - 1) * page_size
                    result = result.limit(page_size).offset(offset)
                    result = [self.serialize(instance, only=fields)
                              for instance in result]
                # Create the pagination link URLs
                #
                # TODO pagination needs to respect sorting, fields, etc., so
                # these link template strings are not quite right.
                base_url = request.base_url
                link_urls = (LINKTEMPLATE.format(base_url, num, page_size)
                             if num is not None else None
                             for rel, num in (('first', first), ('last', last),
                                              ('prev', prev), ('next', next_)))
                first_url, last_url, prev_url, next_url = link_urls
                # Make them available for the result dictionary later.
                pagination_links = dict(first=first_url, last=last_url,
                                        prev=prev_url, next=next_url)
                link_strings = ('<{0}>; rel="{1}"'.format(url, rel)
                                if url is not None else None
                                for rel, url in (('first', first_url),
                                                 ('last', last_url),
                                                 ('prev', prev_url),
                                                 ('next', next_url)))
                # TODO Should this be multiple header fields, like this::
                #
                #     headers = [('Link', link) for link in link_strings
                #                if link is not None]
                #
                headers = dict(Link=','.join(link for link in link_strings
                                             if link is not None))
        # Otherwise, the result of the search was a single resource.
        else:
            # (This is not a pretty solution.) Set number of results to
            # ``None`` to indicate that the returned JSON metadata should not
            # include a ``total`` key.
            num_results = None
            primary_key = self.primary_key or primary_key_name(result)
            result = self.serialize(result, only=fields)
            # The URL at which a client can access the instance matching this
            # search query.
            url = '{0}/{1}'.format(request.base_url, result[primary_key])
            headers = dict(Location=url)

        # Wrap the resulting object or list of objects under a `data` key.
        result = dict(data=result)

        # Provide top-level links.
        #
        # TODO use a defaultdict for result, then cast it to a dict at the end.
        if 'links' not in result:
            result['links'] = dict()
        result['links']['self'] = url_for(self.model)
        result['links'].update(pagination_links)

        for postprocessor in self.postprocessors['GET_COLLECTION']:
            postprocessor(result=result, filters=filters, sort=sort,
                          single=single)

        # HACK Provide the headers directly in the result dictionary, so that
        # the :func:`jsonpify` function has access to them. See the note there
        # for more information.
        result['meta'] = {_HEADERS: headers}
        result['meta']['total'] = 1 if num_results is None else num_results
        return result, 200, headers

    # TODO break this up into multiple methods: get_resource(),
    # get_related_resource(), get_one_of related_resource()
    def _get_single(self, instid, relationname=None, relationinstid=None):
        for preprocessor in self.preprocessors['GET_RESOURCE']:
            temp_result = preprocessor(instance_id=instid)
            # Let the return value of the preprocessor be the new value of
            # instid, thereby allowing the preprocessor to effectively specify
            # which instance of the model to process on.
            #
            # We assume that if the preprocessor returns None, it really just
            # didn't return anything, which means we shouldn't overwrite the
            # instid.
            if temp_result is not None:
                instid = temp_result
        # get the instance of the "main" model whose ID is instid
        instance = get_by(self.session, self.model, instid, self.primary_key)
        if instance is None:
            message = 'No instance with ID {0}'.format(instid)
            return error_response(404, detail=message)
        is_collection = False
        primary_model = self.model

        # Get related instance instances as a primary resource or collection,
        # if requested.
        if relationname is not None:
            primary_model = get_related_model(self.model, relationname)
            if primary_model is None:
                detail = 'No such relation: {0}'.format(primary_model)
                return error_response(404, detail=detail)
            if is_like_list(instance, relationname):
                instances = getattr(instance, relationname)
                is_collection = True
                if relationinstid is not None:
                    if not any(primary_key_value(instance) == relationinstid
                               for instance in instances):
                        detail = ('No related instance with ID'
                                  ' {0}').format(relationinstid)
                        return error_response(404, detail=detail)
                    instance = get_by(self.session, primary_model,
                                      relationinstid)
                    is_collection = False
            else:
                instance = getattr(instance, relationname)
                if relationinstid is not None:
                    detail = 'Cannot specify ID for a to-one relationship'
                    return error_response(400, detail=detail)

        # Get instances to include.
        if is_collection:
            to_include = set(chain(self.instances_to_include(instance)
                                   for instance in instances))
        else:
            to_include = self.instances_to_include(instance)

        # Get the fields to include for each type of object.
        fields = parse_sparse_fields()

        # Serialize the primary resource or collection or resources.
        fields_for_primary = fields.get(collection_name(primary_model))
        try:
            if is_collection:
                result = [self.serialize(inst, only=fields_for_primary)
                          for inst in instances]
            else:
                result = self.serialize(instance, only=fields_for_primary)
        except SerializationException as exception:
            current_app.logger.exception(str(exception))
            detail = 'Failed to deserialize object'
            return error_response(400, detail=detail)

        # Wrap the primary resource or collection of resources in the `data`
        # key.
        result = dict(data=result)

        # Include any requested resources in a compound document.
        included = []
        for included_instance in to_include:
            included_model = get_model(included_instance)
            fields_for_this = fields.get(collection_name(included_model))
            try:
                serialized = self.serialize(included_instance,
                                            only=fields_for_this)
            except SerializationException as exception:
                current_app.logger.exception(str(exception))
                detail = 'Failed to deserialize object'
                return error_response(400, detail=detail)
            included.append(serialized)
        if included:
            result['included'] = included

        # # If no relation is requested, just return the instance. Otherwise,
        # # get the value of the relation specified by `relationname`.
        # if relationname is None:
        #     # Determine the fields to include for this object.
        #     fields_for_this = fields.get(self.collection_name)
        #     try:
        #         result = self.serialize(instance, only=fields_for_this)
        #     except SerializationException as exception:
        #         current_app.logger.exception(str(exception))
        #         detail = 'Failed to deserialize object'
        #         return error_response(400, detail=detail)
        # else:
        #     related_value = getattr(instance, relationname)
        #     related_model = get_related_model(self.model, relationname)
        #     # Determine fields to include for this model.
        #     fields_for_this = fields.get(collection_name(related_model))
        #     if relationinstid is not None:
        #         related_value_instance = get_by(self.session, related_model,
        #                                         relationinstid)
        #         if related_value_instance is None:
        #             detail = ('No relation exists with name'
        #                       ' "{0}"').format(relationname)
        #             return error_response(404, detail=detail)
        #         try:
        #             result = self.serialize(related_value_instance,
        #                                     only=fields_for_this)
        #         except SerializationException as exception:
        #             current_app.logger.exception(str(exception))
        #             detail = 'Failed to deserialize object'
        #             return error_response(400, detail=detail)
        #     else:
        #         # for security purposes, don't transmit list as top-level JSON
        #         if is_like_list(instance, relationname):
        #             # TODO Disabled pagination for now in order to ease
        #             # transition into JSON API compliance.
        #             #
        #             #     result = self._paginated(list(related_value), deep)
        #             #
        #             try:
        #                 result = [self.serialize(inst, only=fields_for_this)
        #                           for inst in related_value]
        #             except SerializationException as exception:
        #                 current_app.logger.exception(str(exception))
        #                 detail = 'Failed to deserialize object'
        #                 return error_response(400, detail=detail)
        #         else:
        #             try:
        #                 result = self.serialize(related_value,
        #                                         only=fields_for_this)
        #             except SerializationException as exception:
        #                 current_app.logger.exception(str(exception))
        #                 detail = 'Failed to deserialize object'
        #                 return error_response(400, detail=detail)
        # if result is None:
        #     return error_response(404)

        for postprocessor in self.postprocessors['GET_RESOURCE']:
            postprocessor(result=result)
        return result, 200

    def instances_to_include(self, instance):
        # if isinstance(original, list):
        #     has_links = any('links' in resource for resource in original)
        # else:
        #     # If the original data is an empty to-one relation, it could be
        #     # None.
        #     has_links = original is not None and 'links' in original
        # if not has_links:
        #     return {}

        # Add any links requested to be included by URL parameters.
        #
        # We expect `toinclude` to be a comma-separated list of relationship
        # paths.
        toinclude = request.args.get('include')
        if toinclude is None and self.default_includes is None:
            return {}
        elif toinclude is None and self.default_includes is not None:
            toinclude = self.default_includes
        else:
            toinclude = set(toinclude.split(','))

        # TODO we should reverse the nested-ness of these for loops:
        # toinclude is likely to be a small list, and `original` could be a
        # very large list, so the latter should be the outer loop.
        result = set()
        for link in toinclude:
            if '.' in link:
                path = link.split('.')
            else:
                path = [link]
            instances = {instance}
            for relation in path:
                if is_like_list(instance, relation):
                    instances = set(chain(getattr(instance, relation)
                                          for instance in instances))
                else:
                    instances = set(getattr(instance, relation)
                                    for instance in instances)
            result |= set(instances)
            # else:
            #     if is_like_list(instance, relation):
            #         result |= set(chain(getattr(instance, relation)
            #                             for instance in instances))
            #     else:
            #         result |= set(getattr(instance, relation)
            #                       for instance in instances)
            # # If the primary data is a resource and not a collection, turn it
            # # into a list anyway.
            # if not isinstance(original, list):
            #     original = [original]
            # for resource in original:
            #     # If the resource has a link with the name specified in
            #     # `toinclude`, then get the type and IDs of that link.
            #     if link in resource['links']:
            #         link_data = resource['links'][link]['linkage']
            #         # If the link is a to-one relation, turn it into a list
            #         # anyway.
            #         if not isinstance(link_data, list):
            #             link_data = [link_data]
            #         for link_object in link_data:
            #             link_type = link_object['type']
            #             link_id = link_object['id']
            #             ids_to_link[link_type].add(link_id)
            #         # else:
            #         #     link_type = link_data['type']
            #         #     link_id = link_data['id']
            #         #     ids_to_link[link_type].add(link_id)
            # # Otherwise, if there is just a single instance, look through
            # # the links to get the IDs of the linked instances.
            # else:
            #     # If the resource has a link with the name specified in
            #     # `toinclude`, then get the type and IDs of that link.
            #     if link in original['links']:
            #         link_data = original['links'][link]['linkage']
            #         if isinstance(link_data, list):
            #             for link_object in link_data:
            #                 link_type = link_object['type']
            #                 link_id = link_object['id']
            #                 ids_to_link[link_type].add(link_id)
            #         else:
            #             link_type = link_data['type']
            #             link_id = link_data['id']
            #             ids_to_link[link_type].add(link_id)
        return result

    def get(self, instid, relationname, relationinstid):
        """Returns a JSON representation of an instance of model with the
        specified name.

        If ``instid`` is ``None``, this method returns the result of a search
        with parameters specified in the query string of the request. If no
        search parameters are specified, this method returns all instances of
        the specified model.

        If ``instid`` is an integer, this method returns the instance of the
        model with that identifying integer. If no such instance exists, this
        method responds with :http:status:`404`.

        """
        if instid is None:
            return self._search()
        # HACK A GET request to a relationship URL, like
        # `/articles/1/links/author` gets routed here because the
        # RelationshipAPI does not have a get() method (since the other methods
        # behave a bit differently; they don't require serialization, for
        # example).
        if relationname == 'links':
            relationname = relationinstid
            relationinstid = None
        return self._get_single(instid, relationname, relationinstid)

    def _delete_many(self):
        """Deletes multiple instances of the model.

        If search parameters are provided via the ``q`` query parameter, only
        those instances matching the search parameters will be deleted.

        If no instances were deleted, this returns a
        :http:status:`404`. Otherwise, it returns a :http:status:`200` with the
        number of deleted instances in the body of the response.

        """
        # try to get search query from the request query parameters
        try:
            filters = json.loads(request.args.get('filter[objects]', '[]'))
        except (TypeError, ValueError, OverflowError) as exception:
            current_app.logger.exception(str(exception))
            return error_response(400, detail='Unable to decode search query')

        for preprocessor in self.preprocessors['DELETE_COLLECTION']:
            preprocessor(filters=filters)

        # perform a filtered search
        try:
            # HACK We need to ignore any ``order_by`` request from the client,
            # because for some reason, SQLAlchemy does not allow calling
            # delete() on a query that has an ``order_by()`` on it. If you
            # attempt to call delete(), you get this error:
            #
            #     sqlalchemy.exc.InvalidRequestError: Can't call Query.delete()
            #     when order_by() has been called
            #
            result = search(self.session, self.model, filters,
                            _ignore_order_by=True)
        except NoResultFound:
            return error_response(404, detail='No result found')
        except MultipleResultsFound:
            return error_response(404, detail='Multiple results found')
        except Exception as exception:
            current_app.logger.exception(str(exception))
            return error_response(400, detail='Unable to construct query')

        # for security purposes, don't transmit list as top-level JSON
        if isinstance(result, Query):
            # Implementation note: `synchronize_session=False`, described in
            # the SQLAlchemy documentation for
            # :meth:`sqlalchemy.orm.query.Query.delete`, states that this is
            # the most efficient option for bulk deletion, and is reliable once
            # the session has expired, which occurs after the session commit
            # below.
            num_deleted = result.delete(synchronize_session=False)
        else:
            self.session.delete(result)
            num_deleted = 1
        self.session.commit()
        for postprocessor in self.postprocessors['DELETE_COLLECTION']:
            postprocessor(num_deleted=num_deleted)
        result = dict(meta=dict(total=num_deleted))
        return result, 200

    def delete(self, instid, relationname, relationinstid):
        """Removes the specified instance of the model with the specified name
        from the database.

        Although :http:method:`delete` is an idempotent method according to
        :rfc:`2616`, idempotency only means that subsequent identical requests
        cannot have additional side-effects. Since the response code is not a
        side effect, this method responds with :http:status:`204` only if an
        object is deleted, and with :http:status:`404` when nothing is deleted.

        If `relationname

        .. versionadded:: 0.12.0
           Added the `relationinstid` keyword argument.

        .. versionadded:: 0.10.0
           Added the `relationname` keyword argument.

        """
        # Check if this is an attempt to DELETE from a related resource URL.
        if (instid is not None and relationname is not None
            and relationinstid is None):
            detail = ('Cannot DELETE from a related resource URL; perhaps you'
                      ' meant to DELETE from {0}/{1}/links/{2}')
            detail = detail.format(self.collection_name, instid, relationname)
            return error_response(403, detail=detail)
        # If no instance ID is provided, this request is an attempt to delete
        # many instances of the model, possibly filtered.
        if instid is None:
            if not self.allow_delete_many:
                detail = 'Server does not allow deleting from a collection'
                return error_response(405, detail=detail)
            return self._delete_many()
        for preprocessor in self.preprocessors['DELETE_RESOURCE']:
            temp_result = preprocessor(instance_id=instid,
                                       relation_name=relationname,
                                       relation_instance_id=relationinstid)
            # See the note under the preprocessor in the get() method.
            if temp_result is not None:
                instid = temp_result
        was_deleted = False
        inst = get_by(self.session, self.model, instid, self.primary_key)
        if relationname is not None:
            # If no such relation exists, return an error to the client.
            if not hasattr(inst, relationname):
                detail = 'No such link: {0}'.format(relationname)
                return error_response(404, detail=detail)
            # If this is a delete of a one-to-many relationship, remove the
            # related instance.
            if relationinstid is not None:
                related_model = get_related_model(self.model, relationname)
                relation = getattr(inst, relationname)
                # if ',' in relationinstid:
                #     ids = relationinstid.split(',')
                # else:
                #     ids = [relationinstid]
                # toremove = (get_by(self.session, related_model, id_) for id_ in
                #             ids)
                # for obj in toremove:
                #     relation.remove(obj)
                toremove = get_by(self.session, related_model, relationinstid)
                relation.remove(toremove)
            else:
                # If there is no link there to delete, return an error.
                if getattr(inst, relationname) is None:
                    detail = ('No linked instance to delete:'
                              ' {0}').format(relationname)
                    return error_response(400, detail=detail)
                # TODO this doesn't apply to a many-to-one endpoint applies
                #
                # if not relationinstid:
                #     msg = ('Cannot DELETE entire "{0}"'
                #            ' relation').format(relationname)
                #     return dict(message=msg), 400
                #
                # Otherwise, remove the related instance.
                setattr(inst, relationname, None)
            was_deleted = len(self.session.dirty) > 0
        elif inst is not None:
            if not isinstance(inst, list):
                inst = [inst]
            for instance in inst:
                self.session.delete(instance)
            was_deleted = len(self.session.deleted) > 0
        self.session.commit()
        for postprocessor in self.postprocessors['DELETE_RESOURCE']:
            postprocessor(was_deleted=was_deleted)
        if not was_deleted:
            detail = 'There was no instance to delete.'
            return error_response(404, detail=detail)
        return {}, 204

    # def _create_single(self, data):
    #     # Getting the list of relations that will be added later
    #     cols = get_columns(self.model)
    #     relations = set(get_relations(self.model))
    #     # Looking for what we're going to set on the model right now
    #     colkeys = set(cols.keys())
    #     fields = set(data.keys())
    #     props = (colkeys & fields) - relations
    #     # Instantiate the model with the parameters.
    #     modelargs = dict([(i, data[i]) for i in props])
    #     instance = self.model(**modelargs)
    #     # Handling relations, a single level is allowed
    #     for col in relations & fields:
    #         submodel = get_related_model(self.model, col)

    #         if type(data[col]) == list:
    #             # model has several related objects
    #             for subparams in data[col]:
    #                 subinst = get_or_create(self.session, submodel,
    #                                         subparams)
    #                 try:
    #                     getattr(instance, col).append(subinst)
    #                 except AttributeError:
    #                     attribute = getattr(instance, col)
    #                     attribute[subinst.key] = subinst.value
    #         else:
    #             # model has single related object
    #             subinst = get_or_create(self.session, submodel,
    #                                     data[col])
    #             setattr(instance, col, subinst)

    #     # add the created model to the session
    #     self.session.add(instance)
    #     return instance

    def post(self, instid, relationname, relationinstid):
        """Creates a new instance of a given model based on request data.

        This function parses the string contained in
        :attr:`flask.request.data`` as a JSON object and then validates it with
        a validator specified in the constructor of this class.

        The :attr:`flask.request.data` attribute will be parsed as a JSON
        object containing the mapping from field name to value to which to
        initialize the created instance of the model.

        After that, it separates all columns that defines relationships with
        other entities, creates a model with the simple columns and then
        creates instances of these submodels and associates them with the
        related fields. This happens only at the first level of nesting.

        Currently, this method can only handle instantiating a model with a
        single level of relationship data.

        """
        # Check if this is an attempt to POST to a related resource URL.
        if (instid is not None and relationname is not None
            and relationinstid is None):
            detail = ('Cannot POST to a related resource URL; perhaps you'
                      ' meant to POST to {0}/{1}/links/{2}')
            detail = detail.format(self.collection_name, instid, relationname)
            return error_response(403, detail=detail)
        # try to read the parameters for the model from the body of the request
        try:
            data = json.loads(request.get_data()) or {}
        except (BadRequest, TypeError, ValueError, OverflowError) as exception:
            current_app.logger.exception(str(exception))
            return error_response(400, detail='Unable to decode data')
        # apply any preprocessors to the POST arguments
        for preprocessor in self.preprocessors['POST']:
            preprocessor(data=data)
            # # Get the instance on which to set the relationship info.
            # instance = get_by(self.session, self.model, instid)
            # # If no such relation exists, return an error to the client.
            # if not hasattr(instance, relationname):
            #     detail = 'No such link: {0}'.format(relationname)
            #     return error_response(404, detail=detail)
            # related_model = get_related_model(self.model, relationname)
            # relation = getattr(instance, relationname)
            # # If it is -to-many relation, add to the existing list.
            # if is_like_list(instance, relationname):
            #     related_id = data.pop(relationname)
            #     if isinstance(related_id, list):
            #         related_instances = [get_by(self.session, related_model,
            #                                     d) for d in related_id]
            #     else:
            #         related_instances = [get_by(self.session, related_model,
            #                                     related_id)]
            #     relation.extend(related_instances)
            # # Otherwise it is a -to-one relation.
            # else:
            #     # If there is already something there, return an error.
            #     if relation is not None:
            #         detail = ('Cannot POST to a -to-one relationship that'
            #                   ' already has a linked instance (with ID'
            #                   ' {0})').format(relationinstid)
            #         return error_response(400, detail=detail)
            #     # Get the ID of the related model to which to set the link.
            #     #
            #     # TODO I don't know the collection name for the linked objects,
            #     # so I can't provide a correctly named mapping here.
            #     #
            #     # related_id = data[collection_name(related_model)]
            #     related_id = data.popitem()[1]
            #     related_instance = get_by(self.session, related_model,
            #                               related_id)
            #     try:
            #         setattr(instance, relationname, related_instance)
            #     except self.validation_exceptions as exception:
            #         current_app.logger.exception(str(exception))
            #         return self._handle_validation_exception(exception)
            # result = {}
            # status = 204
            # headers = {}
        # else:
        if 'data' not in data:
            detail = 'Resource must have a "data" key'
            return error_response(400, detail=detail)
        data = data['data']
        has_many = isinstance(data, list)
        # Convert the dictionary representation into an instance of the
        # model.
        if has_many:
            # Deserialize each of the models; convert from JSON into
            # instances of a SQLAlchemy model.
            try:
                instances = [self.deserialize(obj) for obj in data]
                self.session.add_all(instances)
                self.session.commit()
            except DeserializationException as exception:
                current_app.logger.exception(str(exception))
                detail = 'Failed to deserialize object'
                return error_response(400, detail=detail)
            except self.validation_exceptions as exception:
                return self._handle_validation_exception(exception)
        else:
            if 'type' not in data:
                detail = 'Must specify correct data type'
                return error_response(400, detail=detail)
            if 'id' in data and not self.allow_client_generated_ids:
                detail = 'Server does not allow client-generated IDS'
                return error_response(403, detail=detail)
            type_ = data.pop('type')
            if type_ != self.collection_name:
                message = ('Type must be {0}, not'
                           ' {1}').format(self.collection_name, type_)
                return error_response(409, detail=message)
            try:
                instance = self.deserialize(data)
                self.session.add(instance)
                self.session.commit()
            except DeserializationException as exception:
                current_app.logger.exception(str(exception))
                detail = 'Failed to deserialize object'
                return error_response(400, detail=detail)
            except self.validation_exceptions as exception:
                return self._handle_validation_exception(exception)
        # Get the dictionary representation of the new instance as it
        # appears in the database.
        if has_many:
            try:
                result = [self.serialize(inst) for inst in instances]
            except SerializationException as exception:
                current_app.logger.exception(str(exception))
                detail = 'Failed to serialize object'
                return error_response(400, detail=detail)
        else:
            try:
                result = self.serialize(instance)
            except SerializationException as exception:
                current_app.logger.exception(str(exception))
                detail = 'Failed to serialize object'
                return error_response(400, detail=detail)
        # Determine the value of the primary key for this instance and
        # encode URL-encode it (in case it is a Unicode string).
        if has_many:
            primary_keys = [primary_key_value(inst, as_string=True)
                            for inst in instances]
        else:
            primary_key = primary_key_value(instance, as_string=True)
        # The URL at which a client can access the newly created instance
        # of the model.
        if has_many:
            urls = ['{0}/{1}'.format(request.base_url, k)
                    for k in primary_keys]
        else:
            url = '{0}/{1}'.format(request.base_url, primary_key)
        # Provide that URL in the Location header in the response.
        #
        # TODO should the many Location header fields be combined into a
        # single comma-separated header field::
        #
        #     headers = dict(Location=', '.join(urls))
        #
        if has_many:
            headers = (('Location', url) for url in urls)
        else:
            headers = dict(Location=url)
        # Wrap the resulting object or list of objects under a 'data' key.
        result = dict(data=result)
        status = 201
        for postprocessor in self.postprocessors['POST']:
            postprocessor(result=result)
        return result, status, headers

    def _update_single(self, instance, data):
        # Update any relationships.
        links = data.pop('links', {})
        for linkname, link in links.items():
            related_model = get_related_model(self.model, linkname)
            # If the client provided "null" for this relation, remove it by
            # setting the attribute to ``None``.
            if link is None:
                setattr(instance, linkname, None)
                continue
            # TODO check for conflicting or missing types here
            # type_ = link['type']

            # If this is a to-many relationship, get all the related
            # resources.
            if isinstance(link, list):
                # Replacement of a to-many relationship may have been disabled
                # by the user.
                if not self.allow_to_many_replacement:
                    message = 'Not allowed to replace a to-many relationship'
                    return error_response(403, detail=message)
                newvalue = [get_by(self.session, related_model, rel['id'])
                            for rel in link]
            # Otherwise, it is a to-one relationship, so just get the single
            # related resource.
            else:
                newvalue = get_by(self.session, related_model, link['id'])
            # If the to-one relationship resource or any of the to-many
            # relationship resources do not exist, return an error response.
            if newvalue is None:
                detail = ('No object of type {0} found'
                          ' with ID {1}').format(link['type'], link['id'])
                return error_response(404, detail=detail)
            elif isinstance(newvalue, list) and any(value is None
                                                    for value in newvalue):
                not_found = (rel for rel, value in zip(link, newvalue)
                             if value is None)
                msg = 'No object of type {0} found with ID {1}'
                errors = [error(detail=msg.format(rel['type'], rel['id']))
                          for rel in not_found]
                return errors_response(404, errors)
            try:
                setattr(instance, linkname, newvalue)
            except self.validation_exceptions as exception:
                current_app.logger.exception(str(exception))
                return self._handle_validation_exception(exception)

        # Check for any request parameter naming a column which does not exist
        # on the current model.
        #
        # Incoming data could be a list or a single resource representation.
        if isinstance(data, list):
            fields = set(chain(data))
        else:
            fields = data.keys()
        for field in fields:
            if not has_field(self.model, field):
                detail = "Model does not have field '{0}'".format(field)
                return error_response(400, detail=detail)

        # if putmany:
        #     try:
        #         # create a SQLALchemy Query from the query parameter `q`
        #         query = create_query(self.session, self.model, search_params)
        #     except Exception as exception:
        #         current_app.logger.exception(str(exception))
        #         return dict(message='Unable to construct query'), 400
        # else:
        for link, value in data.pop('links', {}).items():
            related_model = get_related_model(self.model, link)
            related_instance = get_by(self.session, related_model, value)
            try:
                setattr(instance, link, related_instance)
            except self.validation_exceptions as exception:
                current_app.logger.exception(str(exception))
                return self._handle_validation_exception(exception)
        # Special case: if there are any dates, convert the string form of the
        # date into an instance of the Python ``datetime`` object.
        data = strings_to_datetimes(self.model, data)
        # Try to update all instances present in the query.
        num_modified = 0
        try:
            if data:
                for field, value in data.items():
                    setattr(instance, field, value)
                num_modified += 1
            self.session.commit()
        except self.validation_exceptions as exception:
            current_app.logger.exception(str(exception))
            return self._handle_validation_exception(exception)

    def put(self, instid, relationname, relationinstid):
        """Updates the instance specified by ``instid`` of the named model, or
        updates multiple instances if ``instid`` is ``None``.

        The :attr:`flask.request.data` attribute will be parsed as a JSON
        object containing the mapping from field name to value to which to
        update the specified instance or instances.

        If ``instid`` is ``None``, the query string will be used to search for
        instances (using the :func:`_search` method), and all matching
        instances will be updated according to the content of the request data.
        See the :func:`_search` documentation on more information about search
        parameters for restricting the set of instances on which updates will
        be made in this case.

        This function ignores the `relationname` and `relationinstid` keyword
        arguments.

        .. versionadded:: 0.12.0
           Added the `relationinstid` keyword argument.

        .. versionadded:: 0.10.0
           Added the `relationname` keyword argument.

        """
        # Check if this is an attempt to PUT to a related resource URL.
        if (instid is not None and relationname is not None
            and relationinstid is None):
            detail = ('Cannot PUT to a related resource URL; perhaps you'
                      ' meant to PUT to {0}/{1}/links/{2}')
            detail = detail.format(self.collection_name, instid, relationname)
            return error_response(403, detail=detail)
        # try to load the fields/values to update from the body of the request
        try:
            data = json.loads(request.get_data()) or {}
        except (BadRequest, TypeError, ValueError, OverflowError) as exception:
            # this also happens when request.data is empty
            current_app.logger.exception(str(exception))
            return error_response(400, detail='Unable to decode data')
        for preprocessor in self.preprocessors['PUT_RESOURCE']:
            temp_result = preprocessor(instance_id=instid, data=data)
            # See the note under the preprocessor in the get() method.
            if temp_result is not None:
                instid = temp_result
        # Get the instance on which to set the new attributes.
        instance = get_by(self.session, self.model, instid, self.primary_key)
        # If no instance of the model exists with the specified instance ID,
        # return a 404 response.
        if instance is None:
            detail = 'No instance with ID {0} in model {1}'.format(instid,
                                                                   self.model)
            return error_response(404, detail=detail)
        # Check if this is a request to update a relation.
        if (instid is not None and relationname is not None
            and relationinstid is None):
            related_model = get_related_model(self.model, relationname)
            # Get the ID of the related model to which to set the link.
            #
            # TODO I don't know the collection name for the linked objects, so
            # I can't provide a correctly named mapping here.
            #
            # related_id = data[collection_name(related_model)]
            related_id = data.popitem()[1]
            if isinstance(related_id, list):
                related_instance = [get_by(self.session, related_model, d)
                                    for d in related_id]
            else:
                related_instance = get_by(self.session, related_model,
                                          related_id)
            try:
                setattr(instance, relationname, related_instance)
            except self.validation_exceptions as exception:
                current_app.logger.exception(str(exception))
                return self._handle_validation_exception(exception)
        # This is a request to update an instance of the model.
        else:
            # Unwrap the data from the collection name key.
            data = data.pop('data', {})
            if 'type' not in data:
                message = 'Must specify correct data type'
                return error_response(400, detail=message)
            if 'id' not in data:
                message = 'Must specify resource ID'
                return error_response(400, detail=message)
            type_ = data.pop('type')
            id_ = data.pop('id')
            if type_ != self.collection_name:
                message = ('Type must be {0}, not'
                           ' {1}').format(self.collection_name, type_)
                return error_response(409, detail=message)
            if id_ != instid:
                message = 'ID must be {0}, not {1}'.format(instid, id_)
                return error_response(409, detail=message)
            # If we are attempting to update multiple objects.
            # if isinstance(data, list):
            #     # Check that the IDs specified in the body of the request
            #     # match the IDs specified in the URL.
            #     if not all('id' in d and str(d['id']) in ids for d in data):
            #         msg = 'IDs in body of request must match IDs in URL'
            #         return dict(message=msg), 400
            #     for newdata in data:
            #         instance = get_by(self.session, self.model,
            #                           newdata['id'], self.primary_key)
            #         self._update_single(instance, newdata)
            # else:
            # instance = get_by(self.session, self.model, instid,
            #                   self.primary_key)
            result = self._update_single(instance, data)
            # If result is not None, that means there was an error updating the
            # resource.
            if result is not None:
                return result
        # If we believe that the resource changes in ways other than the
        # updates specified by the request, we must return 200 OK and a
        # representation of the modified resource.
        #
        # TODO This should be checked just once, at instantiation time.
        if changes_on_update(self.model):
            result = dict(data=self.serialize(instance))
            status = 200
        else:
            result = dict()
            status = 204
        # Perform any necessary postprocessing.
        for postprocessor in self.postprocessors['PUT_RESOURCE']:
            postprocessor()
        return result, status


class RelationshipAPI(APIBase):
    # Responds to requests of the form `/people/1/links/articles` and
    # `/articles/1/links/author` with link objects (*not* resource objects).

    def __init__(self, session, model,
                 allow_delete_from_to_many_relationships=False, *args, **kw):
        super(RelationshipAPI, self).__init__(session, model, *args, **kw)
        self.allow_delete_from_to_many_relationships = \
            allow_delete_from_to_many_relationships

    def get(self, instid, relationname):
        for preprocessor in self.preprocessors['GET_RELATIONSHIP']:
            temp_result = preprocessor(instance_id=instid,
                                       relationship=relationname)
            # Let the return value of the preprocessor be the new value of
            # instid, thereby allowing the preprocessor to effectively specify
            # which instance of the model to process on.
            #
            # We assume that if the preprocessor returns None, it really just
            # didn't return anything, which means we shouldn't overwrite the
            # instid.
            if temp_result is not None:
                instid = temp_result
        # get the instance of the "main" model whose ID is instid
        instance = get_by(self.session, self.model, instid, self.primary_key)
        if instance is None:
            detail = 'No instance with ID {0}'.format(instid)
            return error_response(404, detail=detail)
        # If no relation is requested, raise a 404.
        if relationname is None:
            detail = 'Must specify a relationship name.'
            return error_response(404, detail=detail)
        related_value = getattr(instance, relationname)
        related_model = get_related_model(self.model, relationname)
        related_type = collection_name(related_model)
        # For the sake of brevity, rename this function.
        pk = primary_key_value
        # If this is a to-many relationship...
        if is_like_list(instance, relationname):
            # Convert IDs to strings, as required by JSON API.
            #
            # TODO This could be paginated.
            result = [dict(id=str(pk(inst)), type=related_type)
                      for inst in related_value]
        # If this is a to-one relationship...
        else:
            if related_value is None:
                result = None
            else:
                # Convert ID to string, as required by JSON API.
                result = dict(id=str(pk(related_value)), type=related_type)
        # Wrap the result
        result = dict(data=result)
        for postprocessor in self.postprocessors['GET_RELATIONSHIP']:
            postprocessor(result=result)
        return result, 200

    def post(self, instid, relationname):
        # try to load the fields/values to update from the body of the request
        try:
            data = json.loads(request.get_data()) or {}
        except (BadRequest, TypeError, ValueError, OverflowError) as exception:
            # this also happens when request.data is empty
            current_app.logger.exception(str(exception))
            return error_response(400, detail='Unable to decode data')
        for preprocessor in self.preprocessors['POST_RELATIONSHIP']:
            temp_result = preprocessor(instance_id=instid,
                                       relation_name=relationname, data=data)
            # See the note under the preprocessor in the get() method.
            if temp_result is not None:
                instid, relationname = temp_result
        instance = get_by(self.session, self.model, instid, self.primary_key)
        # If no instance of the model exists with the specified instance ID,
        # return a 404 response.
        if instance is None:
            detail = 'No instance with ID {0} in model {1}'.format(instid,
                                                                   self.model)
            return error_response(404, detail=detail)
        # If no such relation exists, return a 404.
        if not hasattr(instance, relationname):
            detail = 'Model {0} has no relation named {1}'.format(self.model,
                                                                  relationname)
            return error_response(404, detail=detail)
        related_model = get_related_model(self.model, relationname)
        related_value = getattr(instance, relationname)
        # Unwrap the data from the request.
        data = data.pop('data', {})
        for rel in data:
            if 'type' not in rel:
                detail = 'Must specify correct data type'
                return error_response(400, detail=detail)
            if 'id' not in rel:
                detail = 'Must specify resource ID'
                return error_response(400, detail=detail)
            type_ = rel['type']
            # The type name must match the collection name of model of the
            # relation.
            if type_ != collection_name(related_model):
                detail = ('Type must be {0}, not'
                          ' {1}').format(collection_name(related_model), type_)
                return error_response(409, detail=detail)
            # Get the new objects to add to the relation.
            new_value = get_by(self.session, related_model, rel['id'])
            if new_value is None:
                detail = ('No object of type {0} found with ID'
                          ' {1}').format(type_, rel['id'])
                return error_response(404, detail=detail)
            # Don't append a new value if it already exists in the to-many
            # relationship.
            if new_value not in related_value:
                try:
                    related_value.append(new_value)
                except self.validation_exceptions as exception:
                    current_app.logger.exception(str(exception))
                    return self._handle_validation_exception(exception)
        # TODO do we need to commit the session here?
        #
        #     self.session.commit()
        #
        # Perform any necessary postprocessing.
        for postprocessor in self.postprocessors['POST_RELATIONSHIP']:
            postprocessor()
        return {}, 204

    def put(self, instid, relationname):
        # try to load the fields/values to update from the body of the request
        try:
            data = json.loads(request.get_data()) or {}
        except (BadRequest, TypeError, ValueError, OverflowError) as exception:
            # this also happens when request.data is empty
            current_app.logger.exception(str(exception))
            return error_response(400, detail='Unable to decode data')
        for preprocessor in self.preprocessors['PUT_RELATIONSHIP']:
            temp_result = preprocessor(instance_id=instid,
                                       relation_name=relationname, data=data)
            # See the note under the preprocessor in the get() method.
            if temp_result is not None:
                instid, relationname = temp_result
        instance = get_by(self.session, self.model, instid, self.primary_key)
        # If no instance of the model exists with the specified instance ID,
        # return a 404 response.
        if instance is None:
            detail = 'No instance with ID {0} in model {1}'.format(instid,
                                                                   self.model)
            return error_response(404, detail=detail)
        # If no such relation exists, return a 404.
        if not hasattr(instance, relationname):
            detail = 'Model {0} has no relation named {1}'.format(self.model,
                                                                  relationname)
            return error_response(404, detail=detail)
        related_model = get_related_model(self.model, relationname)
        # related_value = getattr(instance, relationname)

        # Unwrap the data from the request.
        data = data.pop('data', {})
        # If the client sent a null value, we assume it wants to remove a
        # to-one relationship.
        if data is None:
            # TODO check that the relationship is a to-one relationship.
            setattr(instance, relationname, None)
        else:
            # If this is a list, we assume the client is trying to set a
            # to-many relationship.
            if isinstance(data, list):
                # Replacement of a to-many relationship may have been disabled
                # on the server-side by the user.
                if not self.allow_to_many_replacement:
                    detail = 'Not allowed to replace a to-many relationship'
                    return error_response(403, detail=detail)
                replacement = []
                for rel in data:
                    if 'type' not in rel:
                        detail = 'Must specify correct data type'
                        return error_response(400, detail=detail)
                    if 'id' not in rel:
                        detail = 'Must specify resource ID or IDs'
                        return error_response(400, detail=detail)
                    type_ = rel['type']
                    # The type name must match the collection name of model of
                    # the relation.
                    if type_ != collection_name(related_model):
                        detail = 'Type must be {0}, not {1}'
                        detail = detail.format(collection_name(related_model),
                                               type_)
                        return error_response(409, detail=detail)
                    id_ = rel['id']
                    obj = get_by(self.session, related_model, id_)
                    replacement.append(obj)
            # Otherwise, we assume the client is trying to set a to-one
            # relationship.
            else:
                if 'type' not in data:
                    detail = 'Must specify correct data type'
                    return error_response(400, detail=detail)
                if 'id' not in data:
                    detail = 'Must specify resource ID or IDs'
                    return error_response(400, detail=detail)
                type_ = data['type']
                # The type name must match the collection name of model of the
                # relation.
                if type_ != collection_name(related_model):
                    detail = ('Type must be {0}, not'
                              ' {1}').format(collection_name(related_model),
                                             type_)
                    return error_response(409, detail=detail)
                id_ = data['id']
                replacement = get_by(self.session, related_model, id_)
            # If the to-one relationship resource or any of the to-many
            # relationship resources do not exist, return an error response.
            if replacement is None:
                detail = ('No object of type {0} found'
                          ' with ID {1}').format(type_, id_)
                return error_response(404, detail=detail)
            if (isinstance(replacement, list)
                and any(value is None for value in replacement)):
                not_found = (rel for rel, value in zip(data, replacement)
                             if value is None)
                detail = 'No object of type {0} found with ID {1}'
                errors = [error(detail=detail.format(rel['type'], rel['id']))
                          for rel in not_found]
                return errors_response(404, errors)
            # Finally, set the relationship to have the new value.
            try:
                setattr(instance, relationname, replacement)
            except self.validation_exceptions as exception:
                current_app.logger.exception(str(exception))
                return self._handle_validation_exception(exception)
        # TODO do we need to commit the session here?
        #
        #     self.session.commit()
        #
        # Perform any necessary postprocessing.
        for postprocessor in self.postprocessors['PUT_RELATIONSHIP']:
            postprocessor()
        return {}, 204

    def delete(self, instid, relationname):
        if not self.allow_delete_from_to_many_relationships:
            detail = 'Not allowed to delete from a to-many relationship'
            return error_response(403, detail=detail)
        # try to load the fields/values to update from the body of the request
        try:
            data = json.loads(request.get_data()) or {}
        except (BadRequest, TypeError, ValueError, OverflowError) as exception:
            # this also happens when request.data is empty
            current_app.logger.exception(str(exception))
            return error_response(400, detail='Unable to decode data')
        was_deleted = False
        for preprocessor in self.preprocessors['DELETE_RELATIONSHIP']:
            temp_result = preprocessor(instance_id=instid,
                                       relation_name=relationname)
            # See the note under the preprocessor in the get() method.
            if temp_result is not None:
                instid = temp_result
        instance = get_by(self.session, self.model, instid, self.primary_key)
        # If no such relation exists, return an error to the client.
        if not hasattr(instance, relationname):
            detail = 'No such link: {0}'.format(relationname)
            return error_response(404, detail=detail)
        # We assume that the relation is a to-many relation.
        related_model = get_related_model(self.model, relationname)
        relation = getattr(instance, relationname)
        data = data.pop('data')
        for rel in data:
            if 'type' not in rel:
                detail = 'Must specify correct data type'
                return error_response(400, detail=detail)
            if 'id' not in rel:
                detail = 'Must specify resource ID'
                return error_response(400, detail=detail)
            toremove = get_by(self.session, related_model, rel['id'])
            try:
                relation.remove(toremove)
            except ValueError:
                # The JSON API specification requires that we silently ignore
                # requests to delete nonexistent objects from a to-many
                # relation.
                pass
        was_deleted = len(self.session.dirty) > 0
        self.session.commit()
        for postprocessor in self.postprocessors['DELETE_RELATIONSHIP']:
            postprocessor(was_deleted=was_deleted)
        if not was_deleted:
            detail = 'There was no instance to delete'
            return error_response(404, detail=detail)
        return {}, 204
