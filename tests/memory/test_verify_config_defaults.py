from mem0 import Memory

m = Memory()
print(m.config.conflict_detection.similarity_threshold)  # 0.85
print(m.config.conflict_detection.top_k)                 # 20
print(m.config.conflict_detection.auto_resolve_strategy) # "keep-higher-confidence"
print(m.config.conflict_detection.hitl_enabled)          # False
print(m.config.session_id)                               # some UUID string