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

    unittest.main()
