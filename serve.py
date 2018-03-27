from flask import Flask, abort, request

from highfive import event_handlers
from highfive.runner.config import init_logger, get_logger
from highfive.runner import Configuration, Runner

import os

if __name__ == '__main__':
    init_logger()
    logger = get_logger(__name__)

    config = Configuration()
    config_path = os.path.join('highfive', 'config.json')

    # Load the configuration file
    config.load_from_file(config_path)

    # Load the handlers into memory
    event_handlers.load_handlers_using(config)

    # Launch app
    runner = Runner(config)
    app = Flask(config.name)

    @app.route('/', methods=['POST'])
    def handle_payload():
        headers, raw_payload = request.headers, request.data
        sign = headers['X-Hub-Signature']
        status, payload = runner.verify_payload(sign, raw_payload)
        if status is not None:
            abort(status)

        event = headers['X-GitHub-Event'].lower()
        runner.handle_payload(payload, event)
        return 'Yay!', 200


    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
