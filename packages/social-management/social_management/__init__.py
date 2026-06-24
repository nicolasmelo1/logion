"""Local agent tool for running Logion's Discord + X presence.

A small CLI that lets agents help run Logion's socials from local
credentials. Discord posting uses per-channel incoming webhooks;
reading uses a bot token (read-only triage). X posting uses the
official API with a hard cost + confirmation gate. No autonomous
posting — every X write requires explicit operator confirmation.
"""
