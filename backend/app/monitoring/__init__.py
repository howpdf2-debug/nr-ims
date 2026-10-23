"""Monitoring engine (Phase 3). 3a-1 = building blocks: secure SNMPv3 access, vendor profiles, rate maths.

Nothing here talks to the network on import and nothing here writes to a device: the whole package is
READ-ONLY by construction (see ``app/services/snmp_v3.py``).
"""
