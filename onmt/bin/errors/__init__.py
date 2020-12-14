from flask import Blueprint

bp = Blueprint('errors', __name__)

from onmt.bin.errors import handlers