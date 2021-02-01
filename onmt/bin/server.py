#!/usr/bin/env python
import configargparse

from flask import Flask, jsonify, request, Blueprint, render_template
from flask_bootstrap import Bootstrap
from waitress import serve
from onmt.translate import TranslationServer, ServerModelError
import logging
from logging.handlers import RotatingFileHandler

STATUS_OK = "ok"
STATUS_ERROR = "error"


def start(config_file,
          url_root="/translator",
          host="0.0.0.0",
          port=5000,
          debug=False):
    def prefix_route(route_function, prefix='', mask='{0}{1}'):
        def newroute(route, *args, **kwargs):
            return route_function(mask.format(prefix, route), *args, **kwargs)

        return newroute

    if debug:
        logger = logging.getLogger("main")
        log_format = logging.Formatter(
            "[%(asctime)s %(levelname)s] %(message)s")
        file_handler = RotatingFileHandler(
            "debug_requests.log",
            maxBytes=1000000, backupCount=10)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

    app = Flask(__name__)
    app.route = prefix_route(app.route, url_root)

    translation_server = TranslationServer()
    translation_server.start(config_file)

    @app.route('/', methods=['GET'])
    @app.route('/index', methods=['GET'])
    def index():
        return render_template('main/index.html')

    @app.route('/about', methods=['GET'])
    def about():
        return render_template('main/about.html')

    @app.route('/models', methods=['GET'])
    def get_models():
        out = translation_server.list_models()
        print('RESPUESTA' + jsonify(out).get_data(as_text=True))
        return render_template('main/index.html', models=jsonify(out).get_data(as_text=True))

    @app.route('/health', methods=['GET'])
    def health():
        out = {}
        out['status'] = STATUS_OK
        return jsonify(out)

    @app.route('/clone_model/<int:model_id>', methods=['POST'])
    def clone_model(model_id):
        out = {}
        data = request.get_json(force=True)  # todo devuelve None
        timeout = -1
        # if 'timeout' in data:
        #     timeout = data['timeout']
        #     del data['timeout']

        # opt = data.get('opt', None)
        opt = None
        try:
            model_id, load_time = translation_server.clone_model(
                model_id, opt, timeout)
        except ServerModelError as e:
            out['status'] = STATUS_ERROR
            out['error'] = str(e)
        else:
            out['status'] = STATUS_OK
            out['model_id'] = model_id
            out['load_time'] = load_time

        print('RESPUESTA' + jsonify(out).get_data(as_text=True))
        return render_template('main/index.html', clone_model=jsonify(out).get_data(as_text=True))

    @app.route('/unload_model/<int:model_id>', methods=['GET'])
    def unload_model(model_id):
        out = {"model_id": model_id}

        try:
            translation_server.unload_model(model_id)
            out['status'] = STATUS_OK
        except Exception as e:
            out['status'] = STATUS_ERROR
            out['error'] = str(e)

        return jsonify(out)

    @app.route('/translate', methods=['POST'])
    def translate():
        # '[{"id": 1500, "src": "WIND"}]'
        inputs = [{}]  # request.get_json(force=True)
        text = request.form["text_to_translate"].upper()
        print("INPUT: " + text)
        inputs[0] = {"id": 1500, "src": text}
        if debug:
            logger.info(inputs)
        out = {}
        try:
            trans, scores, n_best, _, aligns = translation_server.run(inputs)
            assert len(trans) == len(inputs) * n_best
            assert len(scores) == len(inputs) * n_best
            assert len(aligns) == len(inputs) * n_best

            out = [[] for _ in range(n_best)]
            for i in range(len(trans)):
                response = {"src": inputs[i // n_best]['src'], "tgt": trans[i],
                            "n_best": n_best, "pred_score": scores[i]}
                if aligns[i] is not None:
                    response["align"] = aligns[i]
                out[i % n_best].append(response)
        except ServerModelError as e:
            out['error'] = str(e)
            out['status'] = STATUS_ERROR
        if debug:
            logger.info(out)
        translation = str(out[0][0]['tgt'])
        src = request.form["text_to_translate"]
        best = out[0][0]['n_best']
        score = out[0][0]['pred_score']
        print('RESPUESTA' + jsonify(out).get_data(as_text=True))
        # return render_template('main/index.html', translated_text=jsonify(out).get_data(as_text=True))
        return render_template('main/index.html', translation=translation, src=src, best=best, score=score)

    @app.route('/to_cpu/<int:model_id>', methods=['GET'])
    def to_cpu(model_id):
        out = {'model_id': model_id}
        translation_server.models[model_id].to_cpu()

        out['status'] = STATUS_OK
        return jsonify(out)

    @app.route('/to_gpu/<int:model_id>', methods=['GET'])
    def to_gpu(model_id):
        out = {'model_id': model_id}
        translation_server.models[model_id].to_gpu()

        out['status'] = STATUS_OK
        return jsonify(out)

    return app
    # serve(app, host=host, port=port)


def _get_parser():
    parser = configargparse.ArgumentParser(
        config_file_parser_class=configargparse.YAMLConfigFileParser,
        description="OpenNMT-py REST Server")
    parser.add_argument("--ip", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default="5000")
    parser.add_argument("--url_root", type=str, default="/translator")
    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--config", "-c", type=str,
                        default="./available_models/conf.json")
    return parser


def main():
    parser = _get_parser()
    args = parser.parse_args()
    start(args.config, url_root=args.url_root, host=args.ip, port=args.port,
          debug=args.debug)


if __name__ == "__main__":
    main()
