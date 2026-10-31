# Entry point for cPanel "Setup Python App" (Phusion Passenger) hosting.
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "marketian.settings")

from marketian.wsgi import application  # noqa: E402,F401
