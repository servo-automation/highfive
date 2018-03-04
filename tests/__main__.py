import imp
import logging
import unittest

if __name__ == '__main__':
    highfive = imp.load_module('highfive', None, 'highfive',
                               ('', '', imp.PKG_DIRECTORY))
    logging.basicConfig(level=logging.CRITICAL)

    from config_tests import ConfigurationTests
    from installation_manager_tests import InstallationManagerTests
    from runner_tests import RunnerTests
    from api_provider_tests import APIProviderTests
    from event_handler_tests import EventHandlerTests
    import handler_tests

    unittest.main(exit=False)       # TODO: This doesn't exit when failure occurs. Use the builder.
    print
    handler_tests.run()
