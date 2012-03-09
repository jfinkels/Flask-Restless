# -*- coding: utf-8; Mode: Python -*-
#
# Copyright 2012 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
    Authentication example using Flask-Login
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This provides a simple example of using Flask-Login as the authentication
    framework which can guard access to certain API endpoints.

    This requires the following Python libraries to be installed:

    * Elixir
    * Flask
    * Flask-Restless
    * Flask-Login
    * Flask-WTF

    To install them using ``pip``, do::

        pip install Elixir Flask Flask-Restless Flask-Login Flask-WTF

    To use this example, run this package from the command-line. If you are
    using Python 2.7 or later::

        python -m authentication

    If you are using Python 2.6 or earlier::

        python -m authentication.__main__

    Attempts to access the URL of the API for the :class:`User` class at
    ``http://localhost:5000/api/user`` will fail with an :http:statuscode:`401`
    because you have not yet logged in. To log in, visit
    ``http://localhost:5000/login`` and login with username ``example`` and
    password ``example``. Once you have successfully logged in, you may now
    make :http:get:`http://localhost:5000/api/user` requests.

    :copyright: 2012 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com>
    :license: GNU AGPLv3, see COPYING for more details

"""
import os
import os.path

from elixir import metadata, setup_all, create_all, session, Field, Unicode
from flask import Flask, render_template, redirect, url_for
from flask.ext.restless import APIManager, Entity
from flask.ext.login import current_user, login_user, LoginManager, UserMixin
from flask.ext.wtf import PasswordField, SubmitField, TextField, Form


# Step 1: create the user database model.
class User(Entity, UserMixin):
    username = Field(Unicode)
    password = Field(Unicode)

# Step 2: setup the database.
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'test.sqlite')
if os.path.exists(DATABASE):
    os.unlink(DATABASE)
metadata.bind = 'sqlite:///{}'.format(DATABASE)
metadata.bind.echo = False
setup_all()
create_all()

# Step 3: create a test user in the database.
user1 = User(username=u'example', password=u'example')
session.commit()

# Step 4: create the Flask application and its login manager.
app = Flask(__name__)
login_manager = LoginManager()
login_manager.setup_app(app)


# Step 5: this is required for Flask-Login.
@login_manager.user_loader
def load_user(userid):
    return User.get(userid)


# Step 6: create the login and add user forms.
class LoginForm(Form):
    username = TextField('username')
    password = PasswordField('password')
    submit = SubmitField('Login')


class AddForm(Form):
    username = TextField('username')
    password = PasswordField('password')
    submit = SubmitField('Login')


# Step 7: create endpoints for the application, one for index and one for login
@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        #
        # you would check username and password here...
        #
        username, password = form.username.data, form.password.data
        user = User.get_by(username=username, password=password)
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html', form=form)

# Step 8: create the API for User.
api_manager = APIManager(app)
auth_func = lambda: current_user.is_authenticated()
api_manager.create_api(User, authentication_required_for=['GET'],
                       authentication_function=auth_func)

# Step 9: configure and run the application
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = os.urandom(24)
app.run()
