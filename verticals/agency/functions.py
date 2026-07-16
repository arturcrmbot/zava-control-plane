from dataclasses import replace

from api.shared.all_functions import FUNCTIONS


AGENCY_FUNCTIONS = {
    name: function
    for name, function in FUNCTIONS.items()
    if name != "customer-success"
}
AGENCY_FUNCTIONS["ops"] = replace(
    AGENCY_FUNCTIONS["ops"],
    owns_domains=("crisis-response",),
)
