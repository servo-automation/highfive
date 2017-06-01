#!/usr/bin/env python

from __future__ import print_function

from helpers.methods import CONFIG_PATH, get_logger
from helpers.runner import Runner

import cgi, json, logging, os, sys

if __name__ == '__main__':
    print("Content-Type: text/plain\r\n")
    print('\r\n')
    logging.basicConfig(level=logging.DEBUG)
    logger = get_logger(__name__)

    with open(CONFIG_PATH, 'r') as fd:
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

    with open(CONFIG_PATH, 'w') as fd:      # caches some API data
        json.dump(runner.config, fd)
