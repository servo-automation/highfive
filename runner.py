from flask import Flask, request

import os, json


if __name__ == '__main__':
    with open('config.json', 'r') as fd:
        config = json.load(fd)

    user = config['login']['user']
    auth_token = config['login']['token']

    app = Flask('highfive')

    @app.route('/', methods=['POST'])
    def handle_payload():
        payload = request.get_json()
        # handle payload
        return 'Yay!', 200

    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
