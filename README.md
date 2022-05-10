# django-anvil-consortium-manager

A Django app to manage Consortium AnVIL groups, workspaces, and access.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

License: MIT


## Using the app

The package is not on PyPI and there are no GitHub releases yet.

Build the app (from this repository):

    $ python -m build

### In your django project:

1. Install the app into your Django project (note: not on PyPI so this doesn't work):

    $ pip install /<path>/<to>/<repo>/dist/django-anvil-consortium-manager-0.0.999.tar.gz

2. In the settings file, add `django_tables2` and `anvil_consortium_manager` to `INSTALLED_PACKAGES`.

3. In the settings file, set the variable `ANVIL_API_SERVICE_ACCOUNT_FILE` to the path the json file with Google service account credentials. You will need to have already created this service account and registered it with Terra/AnVIL.

    $ ANVIL_API_SERVICE_ACCOUNT_FILE = "/<path>/<to>/<service_account>.json"

4. Include the app URLs to the project urls.

    $ path("anvil/", include("anvil_consortium_manager.urls"))

## Developer set up

### Initial setup

Clone the repository:

    $ git clone git@github.com:UW-GAC/django-anvil-consortium-manager.git

Set up the environment:

    $ python -m venv venv
    $ source venv/bin/activate
    $ pip install -r requirements/dev.txt

Run the example site:

    $ python manage.py migrate
    $ python manage.py createsuperuser
    $ python manage.py runserver

### Tests

#### Using the test script

    $ ./runtests.py

#### Using pytest

    $ pytest

#### Test coverage

To run the tests, check your test coverage, and generate an HTML coverage report:

    $ coverage run ./runtests.py
    $ coverage html
    $ open htmlcov/index.html


### Maria DB setup

By default, the Django settings file uses a SQLite backend for development.
You can optionally use MariaDB instead for tests by following these steps.

Install MariaDB. Here are some notes:
* [Django docs](https://docs.djangoproject.com/en/4.0/ref/databases/#mysql-notes)
* [Install MariaDB server on Mac with Macports](https://www.sindastra.de/p/1966/how-to-install-mariadb-server-on-mac-with-macports)
* [How to use MySQL or MariaDB with your django application on Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-use-mysql-or-mariadb-with-your-django-application-on-ubuntu-14-04)

One time setup via Macports (note that previous versions are broken on Apple ARM chips):
```
# Install ports.
sudo port install mariadb-10.5
sudo port install mariadb-10.5-server
sudo port select --set mysql mariadb-10.5

# Set up db.
sudo -u _mysql /opt/local/lib/mariadb-10.5/bin/mysql_install_db
sudo chown -R _mysql:_mysql /opt/local/var/db/mariadb-10.5

# Start the server.
sudo -u _mysql /opt/local/lib/mariadb-10.5/bin/mysqld_safe --datadir='/opt/local/var/db/mariadb-10.5' &

# Run secure installation script.
sudo /opt/local/lib/mariadb-10.5/bin/mysql_secure_installation
```

One time database setup. Start mariadb with `sudo mysql -u root -p`, then run these commands:
```
# Create the django database.
CREATE DATABASE anvil_consortium_manager CHARACTER SET utf8;

# Create the django user.
CREATE USER django@localhost IDENTIFIED BY 'password';

# Grant permissions to the django database for the django user.
GRANT ALL PRIVILEGES ON anvil_consortium_manager.* TO django@localhost;

# Same for test database.
CREATE DATABASE test_anvil_consortium_manager CHARACTER SET utf8;
GRANT ALL PRIVILEGES ON test_anvil_consortium_manager.* TO django@localhost;

# Apply changes.
> FLUSH PRIVILEGES;
```

To run tests using MariaDB as the backend, run:

```
(export DJANGO_SETTINGS_FILE=anvil_consortium_manager.tests.settings.local_mariadb ; ./runtests.py)
```

```
pytest --ds=anvil_consortium_manager.tests.settings.local_mariadb
```
