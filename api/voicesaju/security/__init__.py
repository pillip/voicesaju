"""Security primitives for VoiceSaju.

- `envelope`: per-row AES-256-GCM envelope encryption (data_model §4.25, NFR-005).
- `kms`: KMSProvider protocol + LocalKMS for dev (KEK from env).
"""

from voicesaju.security import envelope, kms

__all__ = ["envelope", "kms"]
