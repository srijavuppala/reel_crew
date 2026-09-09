"""Scene-heading vocabulary, shared by the planner and the crew derivation.

Both modules need to agree on what counts as night: the planner prices it as
schedule risk, and the crew derivation turns it into a gaffer and a key grip.
Keeping the definition in one place stops those two answers from drifting apart.
"""
from __future__ import annotations

import re

# Final Draft, Word autocorrect and PDF exports all emit en/em dashes in
# sluglines, so a separator that only understands "-" loses the time of day on
# a large share of real scripts.
DASHES = re.compile(r"[‐-―−]")
SEPARATOR = re.compile(r"\s+-+\s+")

TIME_WORDS = {
    "DAY", "NIGHT", "DAWN", "DUSK", "MORNING", "EVENING", "AFTERNOON", "MIDNIGHT",
    "SUNSET", "SUNRISE", "MAGIC HOUR", "CONTINUOUS", "LATER", "MOMENTS LATER", "SAME",
}
# The subset that costs money: night lighting, turnaround and overtime.
NIGHT_TIMES = {"NIGHT", "DAWN", "DUSK", "MIDNIGHT", "EVENING", "SUNSET", "SUNRISE", "MAGIC HOUR"}


def normalise(heading: str) -> str:
    """Collapse whitespace, upper-case, and fold every dash variant to '-'."""
    return DASHES.sub("-", re.sub(r"\s+", " ", heading.strip().upper()))
