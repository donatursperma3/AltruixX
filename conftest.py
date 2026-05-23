"""
Root conftest.py for Altruix test suite.

This conftest prevents the Main package from being fully initialized
(which would try to start the Telegram bot) when running isolated tests
in Main/tests/ that don't need the full application context.

The self-contained tests in Main/tests/ replicate only the specific logic
under test inline — they do NOT import from the Main package.
"""
import sys
import types
import os

# Pre-populate sys.modules with a stub for 'Main' at module load time
# (before pytest starts collecting tests) so that pytest's package import
# mechanism does not trigger Main/__init__.py (which starts the Telegram bot).
#
# This stub is only installed if Main has not already been imported.
# Tests that need the real Main package should not be in Main/tests/.
if 'Main' not in sys.modules:
    _stub = types.ModuleType('Main')
    _stub.__path__ = [os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Main')]
    _stub.__package__ = 'Main'
    _stub.__spec__ = None
    sys.modules['Main'] = _stub
