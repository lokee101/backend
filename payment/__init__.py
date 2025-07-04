from flask import Blueprint

payment_bp = Blueprint('payment', __name__)

from . import routes # Import routes to register them with the blueprint
