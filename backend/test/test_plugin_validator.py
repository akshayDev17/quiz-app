"""The quiz-tools plugin's validator is a copy of the backend's, so a file the plugin
passes cannot fail on upload. This pins the copy: apart from its header comment and its
own ``Invalid`` class (the plugin cannot import the backend's errors module), it must be
the backend file byte for byte.

Run:  python3 test/test_plugin_validator.py
"""

from __future__ import annotations

import unittest

import helpers  # noqa: F401  (sys.path)

from helpers import BACKEND

BACKEND_COPY = BACKEND / "quiz_app" / "validation.py"
PLUGIN_COPY = BACKEND.parent / "tools" / "quiz_validation.py"
IMPORT = "from .errors import Invalid\n"


class PluginValidatorTest(unittest.TestCase):
    def test_the_plugin_copy_is_the_backend_validator(self):
        backend = BACKEND_COPY.read_text()
        plugin = PLUGIN_COPY.read_text()
        header, _, rest = plugin.partition("from __future__ import annotations\n")
        self.assertTrue(header.startswith("# Self-contained copy of backend/quiz_app/validation.py."))
        start = rest.index("class Invalid(Exception):")
        end = rest.index("\n\n", start) + 1
        plugin_body = "from __future__ import annotations\n" + rest[:start] + IMPORT + rest[end:]
        backend_body = backend[backend.index("from __future__ import annotations\n"):]
        self.assertEqual(plugin_body, backend_body, "re-copy tools/quiz_validation.py from the backend")


if __name__ == "__main__":
    unittest.main()
