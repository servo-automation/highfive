from unittest import TestSuite, TextTestResult, TextTestRunner

import imp
import logging
import sys
import unittest

if __name__ == '__main__':
    highfive = imp.load_module('highfive', None, 'highfive',
                               ('', '', imp.PKG_DIRECTORY))
    logging.basicConfig(level=logging.CRITICAL)

    test_suite = TestSuite()

    from api_provider_tests import APIProviderTests
    from config_tests import ConfigurationTests
    from event_handler_tests import EventHandlerTests
    from installation_manager_tests import InstallationManagerTests
    from json_store_tests import JsonStoreTests
    from runner_tests import RunnerTests

    test_suite.addTests(unittest.makeSuite(APIProviderTests))
    test_suite.addTests(unittest.makeSuite(ConfigurationTests))
    test_suite.addTests(unittest.makeSuite(EventHandlerTests))
    test_suite.addTests(unittest.makeSuite(InstallationManagerTests))
    test_suite.addTests(unittest.makeSuite(JsonStoreTests))
    test_suite.addTests(unittest.makeSuite(RunnerTests))

    test_runner = TextTestRunner(resultclass=TextTestResult, verbosity=2)
    unittest_result = test_runner.run(test_suite)

    import handler_tests
    print
    handler_tests.run()

    if not unittest_result.wasSuccessful():
        sys.exit(1)
