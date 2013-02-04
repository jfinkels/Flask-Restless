#!/usr/bin/env python

# add the current directory to the Python path
import os.path
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    import unittest2 as unittest
except ImportError:
    import unittest
from tests import suite

def main():
    unittest.main(defaultTest='suite')

if __name__ == '__main__':
    main()
