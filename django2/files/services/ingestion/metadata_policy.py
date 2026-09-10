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


def plan_fill_blank_mapping(existing_values, incoming_values):
    """Apply the importer metadata policy to two dictionaries without mutation."""
    updates = {}
    conflicts = []
    for field, incoming in incoming_values.items():
        if incoming in BLANK_VALUES:
            continue
        existing = existing_values.get(field)
        if existing in BLANK_VALUES:
            updates[field] = incoming
        elif existing != incoming:
            conflicts.append({
                "field": field,
                "existing": existing,
                "incoming": incoming,
            })
    return updates, conflicts
