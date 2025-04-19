#!/usr/bin/env python3
"""
Test runner for the Travel Agent system.
Provides a convenient way to run all tests or specific test categories.
"""

import unittest
import sys
import os
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("test_runner")

def discover_and_run_tests(test_dir, pattern="test_*.py", verbosity=2):
    """
    Discover and run tests in the specified directory.
    
    Args:
        test_dir: Directory containing tests
        pattern: Pattern to match test files
        verbosity: Test result verbosity level
        
    Returns:
        Test result object
    """
    logger.info(f"Discovering tests in {test_dir} matching pattern '{pattern}'")
    
    start_dir = os.path.join(os.path.dirname(__file__), test_dir)
    
    # Check if directory exists
    if not os.path.exists(start_dir):
        logger.error(f"Test directory not found: {start_dir}")
        return None
    
    # Discover and load tests
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir, pattern=pattern)
    
    # Count tests
    test_count = suite.countTestCases()
    logger.info(f"Found {test_count} tests to run")
    
    if test_count == 0:
        logger.warning(f"No tests found in {start_dir} matching pattern '{pattern}'")
        return None
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    return runner.run(suite)

def run_unit_tests(verbosity=2):
    """Run unit tests."""
    logger.info("Running unit tests...")
    return discover_and_run_tests("unit", verbosity=verbosity)

def run_integration_tests(verbosity=2):
    """Run integration tests."""
    logger.info("Running integration tests...")
    return discover_and_run_tests("integration", verbosity=verbosity)

def run_api_tests(verbosity=2):
    """Run API tests."""
    logger.info("Running API tests...")
    return discover_and_run_tests("api", verbosity=verbosity)

def run_end_to_end_tests(verbosity=2):
    """Run end-to-end tests."""
    logger.info("Running end-to-end tests...")
    return discover_and_run_tests("end_to_end", verbosity=verbosity)

def run_all_tests(verbosity=2):
    """Run all tests."""
    logger.info("Running all tests...")
    
    results = []
    
    # Run each test category
    results.append(("Unit Tests", run_unit_tests(verbosity)))
    results.append(("Integration Tests", run_integration_tests(verbosity)))
    results.append(("API Tests", run_api_tests(verbosity)))
    results.append(("End-to-End Tests", run_end_to_end_tests(verbosity)))
    
    # Print summary
    logger.info("\n\n=== TEST SUMMARY ===")
    
    any_failures = False
    for name, result in results:
        if result:
            success = result.wasSuccessful()
            run_count = result.testsRun
            failure_count = len(result.failures)
            error_count = len(result.errors)
            skip_count = len(result.skipped) if hasattr(result, 'skipped') else 0
            
            status = "PASSED" if success else "FAILED"
            logger.info(f"{name}: {status} ({run_count} run, {failure_count} failures, {error_count} errors, {skip_count} skipped)")
            
            if not success:
                any_failures = True
        else:
            logger.info(f"{name}: NO TESTS RUN")
    
    return 1 if any_failures else 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Travel Agent tests")
    
    parser.add_argument(
        "--type", "-t",
        choices=["all", "unit", "integration", "api", "end_to_end"],
        default="all",
        help="Type of tests to run (default: all)"
    )
    
    parser.add_argument(
        "--verbosity", "-v",
        type=int,
        choices=[0, 1, 2],
        default=2,
        help="Verbosity level (0-2, default: 2)"
    )
    
    parser.add_argument(
        "--pattern", "-p",
        type=str,
        default="test_*.py",
        help="Pattern to match test files (default: test_*.py)"
    )
    
    args = parser.parse_args()
    
    # Run tests based on type
    exit_code = 0
    
    if args.type == "all":
        exit_code = run_all_tests(args.verbosity)
    elif args.type == "unit":
        result = run_unit_tests(args.verbosity)
        exit_code = 0 if result and result.wasSuccessful() else 1
    elif args.type == "integration":
        result = run_integration_tests(args.verbosity)
        exit_code = 0 if result and result.wasSuccessful() else 1
    elif args.type == "api":
        result = run_api_tests(args.verbosity)
        exit_code = 0 if result and result.wasSuccessful() else 1
    elif args.type == "end_to_end":
        result = run_end_to_end_tests(args.verbosity)
        exit_code = 0 if result and result.wasSuccessful() else 1
    
    sys.exit(exit_code)
