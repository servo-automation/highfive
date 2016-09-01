from flask import Flask, request

from helpers.api_provider import GithubAPIProvider
from helpers.methods import get_handlers

import os, json, random


if __name__ == '__main__':
    with open('config.json', 'r') as fd:
        config = json.load(fd)

    choice = random.choice(config['logins'])    # pseudo-random choice of bot
    user = choice['user']
    auth_token = choice['token']
    events = config.get('enabled_events', [])
    secret = config.get('secret')

    app = Flask('highfive')

    @app.route('/', methods=['POST'])
    def handle_payload():
        payload = request.get_json()
        if secret:
            # FIXME: ensure that the payload is from Github
            # (verify the signature against hash of the secret)
            pass

        api = GithubAPIProvider(payload, user, auth_token)
        for _, handler in get_handlers(events):
            handler(api)
        return 'Yay!', 200

    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
