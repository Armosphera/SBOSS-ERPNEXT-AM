"""
Bare test runner for verify-isolation tests — no pytest dependency.
Usage: python3 tools/swarm/tests/run_verify_isolation_tests.py
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_verify_isolation import (  # noqa: E402
    TestGlobOverlap,
    TestParseTaskGlobs,
    TestWrapperEndToEnd,
)

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite([
        loader.loadTestsFromTestCase(TestGlobOverlap),
        loader.loadTestsFromTestCase(TestParseTaskGlobs),
        loader.loadTestsFromTestCase(TestWrapperEndToEnd),
    ])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
