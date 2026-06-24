"""
Bare test runner for codegen tests — no pytest dependency.
Usage: python tools/swarm/tests/run_codegen_tests.py
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_codegen import (  # noqa: E402
    TestParseTaskRow, TestParsePlan, TestRenderTaskFile,
    TestBranchPrefixMapping, TestCodegenEndToEnd,
)

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite([
        loader.loadTestsFromTestCase(TestParseTaskRow),
        loader.loadTestsFromTestCase(TestParsePlan),
        loader.loadTestsFromTestCase(TestRenderTaskFile),
        loader.loadTestsFromTestCase(TestBranchPrefixMapping),
        loader.loadTestsFromTestCase(TestCodegenEndToEnd),
    ])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
