from StringIO import StringIO
from flask import Flask, abort, request
from threading import Thread

from helpers.methods import CONFIG_PATH, get_logger
from helpers.runner import Runner

import json, logging, os

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = get_logger(__name__)

    with open(CONFIG_PATH, 'r') as fd:
        config = json.load(fd)

    dump_path = config['dump_path']
    if not os.path.isdir(dump_path):
        logger.debug('Creating dump path: %s', dump_path)
        os.mkdir(dump_path)

    runner = Runner(config)
    sync_thread = Thread(target=runner.start_sync)
    sync_thread.daemon = True
    sync_thread.start()
    app = Flask(config['name'])

    @app.route('/', methods=['POST'])
    def handle_payload():
        headers, raw_payload = request.headers, request.data
        sign = headers['X-Hub-Signature']
        status, payload = runner.verify_payload(sign, StringIO(raw_payload))
        if status is not None:
            abort(status)

        event = headers['X-GitHub-Event'].lower()
        runner.handle_payload(payload, event)
        return 'Yay!', 200


    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
