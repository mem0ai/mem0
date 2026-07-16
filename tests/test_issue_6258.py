else:
    # Unknown operator, treat as equality
    chroma_condition[key] = {"$eq": val}
