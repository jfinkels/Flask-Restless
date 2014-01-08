Downloading and installing Flask-Restless
=========================================

Flask-Restless can be downloaded from `its page on the Python Package Index
<http://pypi.python.org/pypi/Flask-Restless>`_. The development version can be
downloaded from `its page at GitHub
<http://github.com/jfinkels/flask-restless>`_. However, it is better to install
with ``pip`` (hopefully in a virtual environment provided by ``virtualenv``)::

    pip install Flask-Restless

Flask-Restless has the following dependencies (which will be automatically
installed if you use ``pip``):

* `Flask <http://flask.pocoo.org>`_ version 0.9 or greater
* `SQLAlchemy <http://sqlalchemy.org>`_
* `python-dateutil <http://labix.org/python-dateutil>`_ version strictly
  greater than 2.0 if you are using Python 2.6 or Python 2.7, version strictly
  less than 2.0 if you are using Python 2.5
* `simplejson <http://pypi.python.org/pypi/simplejson>`_, *only if* you are
  using Python 2.5
* `Flask-SQLAlchemy <http://packages.python.org/Flask-SQLAlchemy>`_, *only if*
  you want to define your models using Flask-SQLAlchemy (which we highly
  recommend)

Flask-Restless requires Python version 2.5, 2.6 or 2.7. Python 3 support will
come when Flask has it.
