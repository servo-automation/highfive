import imp
import unittest

if __name__ == '__main__':
    highfive = imp.load_module('highfive', None, 'highfive',
                               ('', '', imp.PKG_DIRECTORY))

    from config_tests import ConfigurationTests

    unittest.main()
