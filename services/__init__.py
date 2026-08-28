"""
Services Package for ATOA Backend.
Exposes verification oracle and escrow services.
"""
from services.verification_oracle import verify_deliverable, verify_deliverable_sync

__all__ = ["verify_deliverable", "verify_deliverable_sync"]
