# -*- coding: utf-8 -*-
"""
st_loader.py
============
Imports sentence-transformers, with a fallback for locked-down Windows machines.

On some Windows PCs, "Smart App Control" / an Application Control policy blocks
the compiled files of scikit-learn, so `import sentence_transformers` fails with
"DLL load failed ... An Application Control policy has blocked this file",
even though scikit-learn is only used by features we never call (we only need
model.encode()).

When (and only when) the normal import fails with that kind of error, we
register tiny stand-ins for the few scikit-learn modules that
sentence-transformers / transformers import, and import again. Any code that
really tried to use scikit-learn would then raise a clear error; plain
embedding generation does not use it.
"""

import sys
import types
from importlib.machinery import ModuleSpec

_STUBBED_MODULES = (
    "sklearn",
    "sklearn.base",
    "sklearn.metrics",
    "sklearn.metrics.pairwise",
    "sklearn.utils",
    "sklearn.preprocessing",
    "sklearn.cluster",
    "sklearn.decomposition",
)


class _Stub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def _unavailable(*args, **kwargs):
            raise RuntimeError(
                f"{self.__name__}.{name} needs scikit-learn, which is blocked on this machine"
            )

        return _unavailable


def _install_stubs():
    for name in _STUBBED_MODULES:
        mod = _Stub(name)
        mod.__path__ = []
        mod.__spec__ = ModuleSpec(name, None, is_package=True)
        sys.modules[name] = mod


def _purge(prefixes):
    for name in list(sys.modules):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            del sys.modules[name]


def load_sentence_transformer():
    """Return the SentenceTransformer class, or raise ImportError."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer
    except ImportError as first_error:
        msg = str(first_error)
        if "DLL load failed" not in msg and "Application Control" not in msg:
            raise
        # Windows blocked scikit-learn: retry with stand-ins.
        _purge(("sentence_transformers", "transformers", "sklearn"))
        _install_stubs()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise first_error
        print("  (note: scikit-learn is blocked by Windows on this machine; "
              "using a stand-in. Embeddings are not affected.)")
        return SentenceTransformer
