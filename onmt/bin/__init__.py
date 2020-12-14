
from flask_bootstrap import Bootstrap

from onmt.bin import server
from onmt.bin.config_file import Config


def create_app(config_class=Config):
    app = server.start(config_file="/home/pedro/marina/tfg/transformer-slt-TFG2/onmt/bin/config _file.json")

    Bootstrap(app)

    from onmt.bin.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from flask import Blueprint
    bp = Blueprint('main', __name__)
    app.register_blueprint(bp)

    return app


from onmt.bin import server
