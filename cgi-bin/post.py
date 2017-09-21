#!/usr/bin/env python

from __future__ import print_function

from helpers.methods import CONFIG, get_logger, init_logger
from helpers.runner import Runner

import cgi, json, os, sys

if __name__ == '__main__':
    print("Content-Type: text/plain\r\n")
    print('\r\n')
    init_logger()
    logger = get_logger(__name__)

    config = CONFIG
    auth_path = os.path.join(CONFIG['dump_path'], 'config_dump')
    if os.path.exists(auth_path):
        with open(auth_path, 'r') as fd:
            config = json.load(fd)

    runner = Runner(config)

    if os.environ.get('SYNC'):
        runner.check_installations()
        runner.poke_data()
    else:
        sign = os.environ['HTTP_X_HUB_SIGNATURE']
        event = os.environ['HTTP_X_GITHUB_EVENT'].lower()
        _status, payload = runner.verify_payload(sign, sys.stdin.read())
        if payload is not None:
            runner.handle_payload(payload, event)

    runner.clear_queue()

    with open(auth_path, 'w') as fd:        # caches some API data
        json.dump(runner.config, fd)
