# Catalogue Service for Web

Catalogue service for spatial records over HTTP in the Department of
Biodiversity, Conservation and Attractions.

# Installation

The recommended way to set up this project for development is using
[Poetry](https://python-poetry.org/docs/) to install and manage a virtual Python
environment. With Poetry installed, change into the project directory and run:

    poetry install

To run Python commands in the virtualenv, thereafter run them like so:

    poetry run python manage.py

Manage new or updating project dependencies with Poetry also, like so:

    poetry add newpackage==1.0

# Environment variables

This project uses environment variables (in a `.env` file) to define application settings.
Required settings are as follows:

    DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
    SECRET_KEY="ThisIsASecretKey"

# Running

Use `runserver` to run a local copy of the application:

    poetry run python manage.py runserver 0:8080

Run console commands manually:

    poetry run python manage.py shell_plus

# Media uploads

The production system stores media uploads in Azure blob storage.
Credentials for doing so should be defined in the following environment
variables:

    AZURE_ACCOUNT_NAME=name
    AZURE_ACCOUNT_KEY=key
    AZURE_CONTAINER=container_name

To bypass this and use local media storage (for development, etc.), set
the `LOCAL_MEDIA_STORAGE=True` environment variable and create a writable
`media` directory in the project directory.

# Docker image

To build a new Docker image from the `Dockerfile`:

    docker image build -t ghcr.io/dbca-wa/csw .
