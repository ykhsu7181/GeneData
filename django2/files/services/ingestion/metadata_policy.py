BLANK_VALUES = (None, "")


def plan_fill_blank_metadata(instance, incoming_values):
    """Return blank-field updates and nonblank conflicts without mutating the instance."""
    updates = {}
    conflicts = []
    for field, incoming in incoming_values.items():
        if incoming in BLANK_VALUES:
            continue
        existing = getattr(instance, field)
        if existing in BLANK_VALUES:
            updates[field] = incoming
        elif existing != incoming:
            conflicts.append(
                {
                    "field": field,
                    "existing": existing,
                    "incoming": incoming,
                }
            )
    return updates, conflicts
