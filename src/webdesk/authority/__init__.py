"""Trusted authentication authority (R4, Amendment A2).

The authority is the only component that verifies passwords, writes credentials, issues and
validates sessions, and issues operation proofs. It connects with its own restricted database login
(role webdesk_authority). The ordinary application login has no privilege on credentials, sessions
or proofs.
"""
