#!/usr/bin/env python

from __future__ import print_function

from helpers.methods import ROOT, get_logger
from helpers.runner import Runner

import cgi, json, logging, os

CONFIG_PATH = os.path.join(ROOT, 'config.json')

if __name__ == '__main__':
    print("Content-Type: text/plain\r\n")
    print('\r\n')
    logging.basicConfig(level=logging.DEBUG)
    logger = get_logger(__name__)

    with open(CONFIG_PATH, 'r') as fd:
        config = json.load(fd)

    dump_path = config['dump_path']
    if not os.path.isdir(dump_path):
        logger.debug('Creating dump path: %s', dump_path)
        os.mkdir(dump_path)

    runner = Runner(config)
    if os.environ.get('SYNC'):
        runner.poke_data()
    else:
        sign = os.environ['HTTP_X_HUB_SIGNATURE']
        event = os.environ['HTTP_X_GITHUB_EVENT'].lower()
        payload = runner.verify_payload(sign)
        if payload is not None:
            runner.handle_payload(payload, event)

    with open(CONFIG_PATH, 'w') as fd:      # caches some data
        json.dump(runner.config, fd)
