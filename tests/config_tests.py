from highfive.runner.config import Configuration

from unittest import TestCase

import json
import os


class ConfigurationTests(TestCase):
    def test_config_load(self):
        config = Configuration()
        config_dict = {
            'foo': 'bar',
            'hello': 2,
            'baz': None,
        }

        raw_config = json.dumps(config_dict)
        config.load_from_string(raw_config)
        self.assertEqual(config['foo'], 'bar')
        self.assertEqual(config['hello'], 2)
        self.assertEqual(config['baz'], None)

    def test_config_env_replace(self):
        config = Configuration()
        os.environ['BAZ'] = 'foobar'
        config_dict = { 'baz': 'ENV::BAZ' }
        raw_config = json.dumps(config_dict)
        config.load_from_string(raw_config)
        self.assertEqual(config['baz'], 'foobar')
