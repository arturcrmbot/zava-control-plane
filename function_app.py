"""Azure Functions entry point for the selected vertical pack."""
from __future__ import annotations

from api.shared.vertical_loader import active_runtime


_runtime = active_runtime()
_module = _runtime.pack.durable_functions.load_module()
app = _module.app

# Preserve direct imports used by focused unit tests while exporting only the
# active pack's trigger functions.
for _name, _value in vars(_module).items():
    if not _name.startswith("__"):
        globals().setdefault(_name, _value)
