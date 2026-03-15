import sys
import os

# Pure debug script
print(f"Current Dir: {os.getcwd()}")
print(f"File Dir: {os.path.dirname(__file__)}")

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, root)
print(f"Root added to sys.path: {root}")

try:
    import Main
    print(f"Successfully imported Main: {Main.__file__}")
    print(f"Main is package: {hasattr(Main, '__path__')}")
except Exception as e:
    print(f"Failed to import Main: {e}")

try:
    from Main.internals.settings_handlers import auto_global_purgeme
    print("Successfully imported auto_global_purgeme")
except Exception as e:
    print(f"Failed to import auto_global_purgeme: {e}")
