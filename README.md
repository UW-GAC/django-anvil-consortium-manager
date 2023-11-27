# django-anvil-consortium-manager

A Django app to manage Consortium AnVIL groups, workspaces, and access.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/UW-GAC/django-anvil-consortium-manager/main.svg)](https://results.pre-commit.ci/latest/github/UW-GAC/django-anvil-consortium-manager/main)

License: MIT


## Developer set up

### Initial setup

1. Clone the repository:

```
$ git clone git@github.com:UW-GAC/django-anvil-consortium-manager.git
```

2. Set up the environment:

```
$ hatch env create
```

3. Ask Ben to make a service account and register it with AnVIL.

4. Set an environment variable to specify the path to the service account credentials file:

```
$ export ANVIL_API_SERVICE_ACCOUNT_FILE="/<path>/<to>/<service_account>.json"
```

You can also create a .env file to store environment variables.

5. Run the example site:

```
hatch shell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Tests

To run quick tests:

```
hatch run test
```

To run the full set of tests using different python versions, different django versions, and different backends, run:

```
hatch run all
```

This will also run test coverage and create an html report to view.


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

# Shut down and restart
sudo mysqladmin shutdown

# Properly starting and stopping the server
sudo port load mariadb-10.5-server
sudo port unload mariadb-10.5-server
```

One time database setup. Start mariadb with `sudo mysql -u root -p`, then run these commands:
```
# Create the django database.
CREATE DATABASE anvil_consortium_manager CHARACTER SET utf8;

# Create the django user.
CREATE USER django@localhost IDENTIFIED BY 'password';
CREATE USER django@127.0.0.1 IDENTIFIED BY 'password';

# Grant permissions to the django database for the django user.
GRANT ALL PRIVILEGES ON anvil_consortium_manager.* TO django@localhost;
GRANT ALL PRIVILEGES ON anvil_consortium_manager.* TO django@127.0.0.1;

# Same for test database.
CREATE DATABASE test_anvil_consortium_manager CHARACTER SET utf8;
GRANT ALL PRIVILEGES ON test_anvil_consortium_manager.* TO django@localhost;
GRANT ALL PRIVILEGES ON test_anvil_consortium_manager.* TO django@127.0.0.1;

# Apply changes.
> FLUSH PRIVILEGES;
```

To run tests using MariaDB as the backend, run:

```
hatch run test-mysql.py3.11-4.2:test
```

If you run into errors with `mysqclient>=2.2`, you may need to set some environment variables before installing mysqlclient:

```
export PKG_CONFIG_PATH="/opt/local/lib/mariadb-10.5/pkgconfig/"
export MYSQLCLIENT_LDFLAGS=`pkg-config --libs libmariadb`
export MYSQLCLIENT_CFLAGS=`pkg-config --cflags libmariadb`
```
