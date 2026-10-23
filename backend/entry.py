"""Worker entrypoint.

Deliberately a shim, and deliberately at the project root rather than inside
the package.

`wrangler.jsonc` names the main module, and wrangler treats that file's
directory as the module root — flattening everything under it. Pointing `main`
at `quiz_app/entry.py` would make `quiz_app/` the root, drop `entry.py` at the
top level with no parent package, and every relative import in it would fail at
boot:

    ImportError: attempted relative import with no known parent package

With the shim at the root, the root is `backend/`, and `quiz_app/` is attached
as an actual package, so its internal relative imports resolve. The real
entrypoint stays where it is, importable and testable.
"""

from quiz_app.entry import Default  # noqa: F401  (re-exported for the runtime)
