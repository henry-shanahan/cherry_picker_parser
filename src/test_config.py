import logging
import tempfile
import os


class TestConfig:
    """Centralized test configuration"""

    @staticmethod
    def setup_logging(level=logging.DEBUG):
        """Set up consistent logging for all tests"""
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('test_debug.log')
            ]
        )

    @staticmethod
    def create_temp_dir():
        """Create temporary directory for test files"""
        return tempfile.mkdtemp(prefix='shipping_parser_test_')

    @staticmethod
    def cleanup_temp_dir(temp_dir):
        """Clean up temporary directory"""
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)