# Flask-Restless #

## Introduction ##

This is Flask-Restless, a [Flask][1] extension which facilitates the creation
of ReSTful APIs. It is compatible with models which have been described using
[Elixir][2], a layer on top of [SQLAlchemy][3].

This document contains some brief instructions concerning installation of
requirements, installation of this extension, configuration and usage of this
extension, and building of documentation.

For more information, check the World Wide Web!

  * [Homepage and documentation](http://packages.python.org/Flask-Restless)
  * [Python Package Index listing](http://pypi.python.org/pypi/Flask-Restless)
  * [Source code repository](http://github.com/jfinkels/flask-restless)

[1]: http://flask.pocoo.org
[2]: http://elixir.ematia.de
[3]: http://sqlalchemy.org

## Copyright license ##

The code comprising this program is copyright 2011 Lincoln de Sousa and 2012
Jeffrey Finkelstein, and is published under the GNU Affero General Public
License, either version 3 or (at your option) any later version. For more
information see the `COPYING` file.

## Contents ##

This is a partial listing of the contents of this package.

* `doc/` - the Sphinx documentation for Flask-Restless
* `examples/` - example applications of Flask-Restless
* `COPYING` - the copyright license under which this program is distributed to
  you (the GNU Affero General Public License version 3)
* `flaskext/restless` - the Python package containing the extension
* `README.md` - this file
* `setup.py` - Python setuptools configuration file for packaging this
  extension

The `flaskext/restless` directory is a Python package containing the following
files:

* `views.py` - the view class which implements the ReSTful API
* `manager.py` - the main class which end users will utilize to create ReSTful
  APIs for their database models
* `model.py` - the base class to use for models for which ReSTful APIs will be
  created
* `search.py` - functions and classes which facilitate searching the database
  on requests which require a search

## Installing ##

This application requires [Python 2.7][4].

This application requires the following libraries to be installed:

* [Flask][1] version 0.7 or greater
* [Elixir][2]
* [SQLAlchemy][3]
* [python-dateutil][5] version less than 2.0

These requirements are also listed in the `requirements.txt` file. Using `pip`
is probably the easiest way to install these:

    pip install -r requirements.txt

or

    pip install Flask Elixir SQLAlchemy python-dateutil

[4]: http://www.python.org/
[5]: http://labix.org/python-dateutil

## Building as a Python egg ##

This package can be built, installed, etc. as a Python egg using the provided
`setup.py` script. For more information, run

    python setup.py --help

## How to use ##

For information on how to use this extension, build the documentation here or
view the version at the project's
[homepage](http://packages.python.org/Flask-Restless).

## Testing ##

The Python unit tests are contained in the `tests/` directory (which is a
Python package). To run the test suite, run the command

    python setup.py test

## Building documentation ##

Flask-Restless requires the following program and supporting library to build
the documentation:

* [Sphinx][6]
* [sphinxcontrib-httpdomain-withpatch][7]

Using `pip` is probably the easiest way to install these:

    pip install sphinx "sphinxcontrib-httpdomain-withpatch==1.1.6-patch2"

The documentation is written for Sphinx in [reStructuredText][8] files in the
`docs/` directory. Documentation for each class and function is provided in the
docstring in the code.

The documentation uses the Flask Sphinx theme. It is included as a git
submodule of this project, rooted at `docs/_themes`. To get the themes, do

    git submodule update --init

Now to build the documentation, run the command

    python setup.py build_sphinx

in the top-level directory. The output can be viewed in a web browser by
opening `docs/_build/html/index.html`.

[6]: http://sphinx.pocoo.org/
[7]: http://packages.python.org/sphinxcontrib-httpdomain/
[8]: http://docutils.sourceforge.net/rst.html

## Authors ##

See the `AUTHORS` file for a list of people who have contributed to this code.

## Artwork ##

The `artwork/flask-restless-small.svg` and
`docs/_static/flask-restless-small.png` are licensed under the
[Creative Commons Attribute-ShareAlike 3.0 license][9]. The original image is a
scan of a (now public domain) illustration by Arthur Hopkins in a serial
edition of "The Return of the Native" by Thomas Hardy published in October
1878.

The `artwork/flask-restless.svg` and `docs/_static/flask-restless.png` are
licensed under the [Flask Artwork License][10].

[9]: http://creativecommons.org/licenses/by-sa/3.0
[10]: http://flask.pocoo.org/docs/license/#flask-artwork-license

## Contact ##

Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com>
