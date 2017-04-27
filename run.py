from flask import Flask, abort, request
from threading import Thread

from helpers.runner import Runner

import json, os

if __name__ == '__main__':
    with open('config.json', 'r') as fd:
        config = json.load(fd)

    dump_path = config['dump_path']
    if not os.path.isdir(dump_path):
        os.mkdir(dump_path)

    runner = Runner(config)
    sync_thread = Thread(target=runner.start_sync)
    sync_thread.start()
    app = Flask(config['name'])

    @app.route('/', methods=['POST'])
    def handle_payload():
        headers, raw_payload = request.headers, request.data
        status, payload = runner.verify_payload(headers, raw_payload)
        if status is not None:
            abort(status)

        if payload:     # if there's a matching event...
            event = headers['X-GitHub-Event'].lower()
            thread = Thread(target=runner.handle_payload, args=(payload, event))
            thread.start()

        return 'Yay!', 200


    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)
