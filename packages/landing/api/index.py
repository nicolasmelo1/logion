# SPDX-License-Identifier: MIT
"""Vercel serverless entrypoint for the landing FastAPI app."""

from landing.main import app

__all__ = ["app"]
