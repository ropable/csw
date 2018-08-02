"""
WSGI config for csw project.
It exposes the WSGI callable as a module-level variable named ``application``.
"""
import confy
from django.core.wsgi import get_wsgi_application
import os
from pathlib import Path

d = Path(__file__).resolve().parents[1]
dot_env = os.path.join(str(d), '.env')
if os.path.exists(dot_env):
    confy.read_environment_file(dot_env)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "csw.settings")
application = get_wsgi_application()
