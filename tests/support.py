# Miscellaneous support for testing
import os
import sys

TEST_DIR = os.path.dirname(__file__)
PARENT_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
sys.path.insert(0, PARENT_DIR)
