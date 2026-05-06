"""
archi3d/wsgi.py — WSGI Application Entry Point
================================================
WSGI (Web Server Gateway Interface) is the protocol used by production servers
like gunicorn or uWSGI to communicate with Django.

In development, Django's runserver handles this automatically.
In production:  gunicorn archi3d.wsgi:application
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archi3d.settings")
application = get_wsgi_application()
