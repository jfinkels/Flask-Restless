"""
    flask.ext.restless.exceptions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Provides helper functions for creating exception responses.

    :copyright: 2013 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com>
    :license: GNU AGPLv3+ or BSD

"""
from werkzeug.exceptions import default_exceptions, HTTPException
from flask import abort, json
from flask import make_response


class JSONHTTPException(HTTPException):
    """A base class for HTTP exceptions with ``Content-Type:
    application/json``.

    The ``description`` attribute of this class must set to a string (*not* an
    HTML string) which describes the error.

    """

    def get_body(self, environ):
        """Overrides :meth:`werkzeug.exceptions.HTTPException.get_body` to
        return the description of this error in JSON format instead of HTML.

        """
        return json.dumps(dict(description=self.get_description(environ)))

    def get_headers(self, environ):
        """Returns a list of headers including ``Content-Type:
        application/json``.

        """
        return [('Content-Type', 'application/json')]


# Adapted from http://flask.pocoo.org/snippets/97
def json_abort(status_code, body=None, headers=None):
    """Same as :func:`flask.abort` but with a JSON response."""
    bases = [JSONHTTPException]
    # Add Werkzeug base class.
    if status_code in default_exceptions:
        bases.insert(0, default_exceptions[status_code])
    error_cls = type('JSONHTTPException', tuple(bases), dict(code=status_code))
    abort(make_response(error_cls(body), status_code, headers or {}))
