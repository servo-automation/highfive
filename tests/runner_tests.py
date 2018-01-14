from highfive.runner import Configuration, Runner

from unittest import TestCase

import json

def create_runner():
    config = Configuration()
    config.name = 'test_app'
    config.secret = 'foobar'
    config.integration_id = '999'
    runner = Runner(config)
    return runner

class RunnerTests(TestCase):
    def test_runner_init(self):
        runner = create_runner()
        self.assertEqual(runner.secret, 'foobar')
        self.assertEqual(runner.integration_id, 999)

    def test_runner_payload_verify(self):
        runner = create_runner()
        raw_data = json.dumps({'foo': 'bar'})
        signature = 'sha1=08511d260b8322ad739a3f34665855ba6044366e'
        code, payload = runner.verify_payload(signature, raw_data)
        self.assertTrue(code is None)
        self.assertTrue(payload is not None)

    def test_runner_invalid_payload(self):
        runner = create_runner()
        code, payload = runner.verify_payload('', '')
        self.assertTrue(payload is None)
        self.assertEqual(code, 400)

    def test_runner_invalid_sign(self):
        runner = create_runner()
        raw_data = json.dumps({'foo': 'bar'})
        signature = 'sha1=0xdeadbeef'
        code, payload = runner.verify_payload(signature, raw_data)
        self.assertTrue(payload is None)
        self.assertEqual(code, 403)
