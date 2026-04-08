"""Shared test fixtures for dashboard tests.

Ensures streamlit is mocked before any dashboard module imports.
Config mocking is handled per-test-file (see test_s3_loader.py pattern).
"""

import sys
from unittest.mock import MagicMock

# Mock streamlit before any dashboard module imports
if "streamlit" not in sys.modules:
    mock_st = MagicMock()
    mock_st.cache_data = lambda **kwargs: (lambda f: f)
    mock_st.cache_resource = lambda **kwargs: (lambda f: f)
    sys.modules["streamlit"] = mock_st
