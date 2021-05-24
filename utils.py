def all_same(*items):
    return True if all(v == items[0] for v in items) else False
