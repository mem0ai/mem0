"""Background workers for the OpenMemory API.

Currently hosts the asynchronous write worker (task_06) that consumes the
persistent write queue and runs the (slow) LLM extraction/persistence out of
band, protecting the local LLM from the concurrency of 200+ agents.
"""
