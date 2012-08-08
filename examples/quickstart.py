import flask
import flask.ext.sqlalchemy
import flask.ext.restless

# Create the Flask application and the Flask-SQLAlchemy object.
app = flask.Flask(__name__)
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
db = flask.ext.sqlalchemy.SQLAlchemy(app)

# Create your Flask-SQLALchemy models as usual but with the following two
# (reasonable) restrictions:
#   1. They must have an id column of type Integer.
#   2. They must have an __init__ method which accepts keyword arguments for
#      all columns (the constructor in flask.ext.sqlalchemy.SQLAlchemy.Model
#      supplies such a method, so you don't need to declare a new one).
class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode, unique=True)
    birth_date = db.Column(db.Date)
    computers = db.relationship('Computer', backref=db.backref('owner',
                                                               lazy='dynamic'))


class Computer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode, unique=True)
    vendor = db.Column(db.Unicode)
    owner_id = db.Column(db.Integer, db.ForeignKey('person.id'))
    purchase_time = db.Column(db.DateTime)



# Create the database tables.
db.create_all()

def populate_data():
    db.drop_all()
    db.create_all()

    someone = Person(name='John')
    db.session.add(someone)
    computer = Computer(name='lixeiro')
    db.session.add(computer)
    someone.computers.append(computer)
    db.session.commit()


# Create the Flask-Restless API manager.
manager = flask.ext.restless.APIManager(app, flask_sqlalchemy_db=db)

# Create API endpoints, which will be available at /api/<tablename> by
# default. Allowed HTTP methods can be specified as well.
manager.create_api(Person, methods=['GET', 'POST', 'DELETE'])
manager.create_api(Computer, methods=['GET'])

@app.before_first_request
def before_first_request():
    populate_data()


# start the flask loop
app.logger.info(repr(app.url_map))
app.run(host="127.0.0.1", port=8080, debug=True)