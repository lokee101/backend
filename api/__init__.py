from flask import Blueprint

api_bp = Blueprint('api', __name__)

from . import routes # Import routes to register them with the blueprint
