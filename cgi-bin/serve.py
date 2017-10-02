from flask import Flask, abort, request
from threading import Thread

from helpers.methods import CONFIG, get_logger, init_logger
from helpers.runner import Runner

import json, os

if __name__ == '__main__':
    init_logger()
    logger = get_logger(__name__)
    if not os.path.exists(CONFIG['dump_path']):
        os.mkdir(CONFIG['dump_path'])

    runner = Runner(CONFIG)
    sync_thread = Thread(target=runner.start_sync)
    sync_thread.daemon = True
    sync_thread.start()
    app = Flask(CONFIG['name'])

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
