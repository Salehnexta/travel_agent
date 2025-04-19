#!/usr/bin/env python3
"""
Test runner for the travel agent system.
Provides a CLI to run specific test categories or all tests.
"""

import argparse
import os
import sys
import unittest
import logging
from typing import List, Optional, Tuple

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_runner")


def discover_tests(start_dir: str, pattern: str = "test_*.py") -> unittest.TestSuite:
    """
    Discover tests in the specified directory.
    
    Args:
        start_dir: Directory to start discovery from
        pattern: Pattern to match test files
        
    Returns:
        TestSuite containing discovered tests
    """
    return unittest.defaultTestLoader.discover(start_dir, pattern=pattern)


def run_tests(test_suite: unittest.TestSuite, verbosity: int = 2) -> Tuple[int, int]:
    """
    Run tests from the specified test suite.
    
    Args:
        test_suite: Test suite to run
        verbosity: Verbosity level
        
    Returns:
        Tuple of (test_count, failure_count)
    """
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(test_suite)
    
    test_count = result.testsRun
    failure_count = len(result.failures) + len(result.errors)
    
    return test_count, failure_count


def create_test_suites(test_type: Optional[str] = None) -> List[Tuple[str, unittest.TestSuite]]:
    """
    Create test suites based on the requested test type.
    
    Args:
        test_type: Type of tests to include (unit, integration, api, end_to_end, or None for all)
        
    Returns:
        List of (description, test_suite) tuples
    """
    tests_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")
    
    test_suites = []
    
    # Unit tests
    if test_type in (None, "unit"):
        suite = discover_tests(os.path.join(tests_dir, "unit"))
        test_suites.append(("Unit Tests", suite))
    
    # Integration tests
    if test_type in (None, "integration"):
        suite = discover_tests(os.path.join(tests_dir, "integration"))
        test_suites.append(("Integration Tests", suite))
    
    # API tests
    if test_type in (None, "api"):
        suite = discover_tests(os.path.join(tests_dir, "api"))
        test_suites.append(("API Tests", suite))
    
    # End-to-End tests
    if test_type in (None, "end_to_end"):
        suite = discover_tests(os.path.join(tests_dir, "end_to_end"))
        test_suites.append(("End-to-End Tests", suite))
    
    # Create a combined suite if requested
    if test_type == "all" or test_type is None:
        combined_suite = unittest.TestSuite()
        for _, suite in test_suites:
            combined_suite.addTest(suite)
        
        # Replace individual suites with combined suite if "all" was explicitly requested
        if test_type == "all":
            test_suites = [("All Tests", combined_suite)]
    
    return test_suites


def main():
    """Run the test runner CLI."""
    parser = argparse.ArgumentParser(description="Travel Agent Test Runner")
    
    parser.add_argument("--type", "-t", 
                        choices=["unit", "integration", "api", "end_to_end", "all"],
                        help="Type of tests to run (default: all)")
    
    parser.add_argument("--specific", "-s",
                        help="Run a specific test module (e.g., 'test_input_validation')")
    
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Increase output verbosity")
    
    args = parser.parse_args()
    
    # Set verbosity level
    verbosity = 2
    if args.verbose:
        verbosity = 3
    
    # Run specific test module if requested
    if args.specific:
        specific_module = args.specific
        if not specific_module.startswith("test_"):
            specific_module = f"test_{specific_module}"
        
        # Try to find and run the specified module
        found = False
        test_types = ["unit", "integration", "api", "end_to_end"]
        
        for test_type in test_types:
            test_path = os.path.join("tests", test_type)
            if not os.path.exists(test_path):
                continue
            
            for file in os.listdir(test_path):
                if file.endswith(".py") and file.startswith(specific_module):
                    module_path = os.path.join(test_path, file)
                    rel_path = os.path.relpath(module_path, ".").replace(".py", "").replace(os.path.sep, ".")
                    
                    logger.info(f"Running specific test module: {rel_path}")
                    suite = unittest.defaultTestLoader.loadTestsFromName(rel_path)
                    count, failures = run_tests(suite, verbosity)
                    
                    logger.info(f"Ran {count} tests with {failures} failures")
                    found = True
                    if failures > 0:
                        return 1
        
        if not found:
            logger.error(f"Could not find test module: {specific_module}")
            return 1
        
        return 0
    
    # Run test suites based on the requested type
    test_suites = create_test_suites(args.type)
    
    total_tests = 0
    total_failures = 0
    
    # Run each test suite
    for description, suite in test_suites:
        print(f"\n{'=' * 80}")
        print(f"Running {description}")
        print(f"{'=' * 80}\n")
        
        count, failures = run_tests(suite, verbosity)
        
        total_tests += count
        total_failures += failures
        
        print(f"\nCompleted {description}: {count} tests, {failures} failures\n")
    
    # Print summary
    print(f"\n{'=' * 80}")
    print(f"Test Summary: {total_tests} tests, {total_failures} failures")
    print(f"{'=' * 80}\n")
    
    return 1 if total_failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
