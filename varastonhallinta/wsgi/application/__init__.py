"""Bring modules together to avoid circular imports."""

from . import flask_app
from .views import products, orders
