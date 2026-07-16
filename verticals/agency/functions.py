from dataclasses import replace

from api.shared.functions import ALL_FUNCTIONS


AGENCY_FUNCTIONS = {
    name: function
    for name, function in ALL_FUNCTIONS.items()
    if name != "customer-success"
}
AGENCY_FUNCTIONS["ops"] = replace(
    AGENCY_FUNCTIONS["ops"],
    owns_domains=("crisis-response",),
)
