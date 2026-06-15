"""Repository maintenance and smoke-test scripts.

Beginner guide:
This package marker lets tests import individual scripts by module name, for
example `scripts.smoke_elevenlabs_realtime_stt_relay`.  Without it, mypy may see
the same script under two different names.
"""
