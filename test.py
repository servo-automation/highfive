from helpers.api_provider import APIProvider
from helpers.methods import HANDLERS_DIR, get_handlers

import json, os

TESTS_DIR = 'tests'


class TestAPIProvider(APIProvider):
    def __init__(self, payload):
        super(TestAPIProvider, self).__init__(payload)

    def get_labels(self):
        return self.labels

    def post_comment(self, comment):
        self.comments.append(comment)


if __name__ == '__main__':
    with open('config.json', 'r') as fd:
        config = json.load(fd)

    events = config.get('enabled_events', [])
    for path, handler in get_handlers(events):
        test_payloads_dir = TESTS_DIR + path.lstrip(HANDLERS_DIR)
        # test stuff
