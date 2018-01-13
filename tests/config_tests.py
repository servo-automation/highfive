from highfive.runner import Configuration

from unittest import TestCase

import json
import os

class ConfigurationTests(TestCase):
    def test_config_load(self):
        '''Test loading of configuration from JSON'''

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
        '''Test appropriate env variable substitution in configuration'''

        config = Configuration()
        os.environ['BAZ'] = 'foobar'
        config_dict = { 'baz': 'ENV::BAZ', 'bar': 'ENV::BAZ' }
        raw_config = json.dumps(config_dict)
        config.load_from_string(raw_config)
        self.assertEqual(config['baz'], 'foobar')
        self.assertEqual(config['bar'], 'foobar')   # multiple occurrences
