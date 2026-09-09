"""Screenplay evidence -> the crew the script actually requires.

Two lists come out of this module, and keeping them separate is the point.

IMDb's principal-crew data covers eight crafts. Those roles can be staffed from
the corpus, so they carry a `category` and Build My Crew ranks real people into
them. Everything else a script demands -- a gaffer for night work, a stunt
coordinator for a fight, an armorer for a weapon -- is just as required, and is
reported with `staffable=False` rather than quietly dropped. A crew plan that
silently omits the armorer because the dataset has no armorers is worse than no
crew plan at all.
"""
from __future__ import annotations

import re

from agent.parse import GENRE_SYNONYMS
from .schema import ProductionBrief, RoleRequirement, Scene

# --------------------------------------------------------------- staffable
# (category, display, department, why it is needed, trigger)
# trigger=None means every narrative production needs it.
CORE = [
    ("director", "Director", "Direction", "Every narrative production needs one."),
    ("producer", "Producer", "Production", "Budget, schedule and delivery accountability."),
    ("cinematographer", "Director of Photography", "Camera",
     "Every scene is photographed; the DP sets the look and the lighting plan."),
    ("editor", "Editor", "Post-production", "Assembly and cut of every scene shot."),
]

CONDITIONAL = [
    ("production_designer", "Production Designer", "Art",
     "distinct locations need a coherent designed world",
     lambda ctx: ctx["locations"] >= 2 or "special effects" in ctx["signals"]),
    ("composer", "Composer", "Music",
     "scored narrative feature",
     lambda ctx: True),
    ("casting_director", "Casting Director", "Casting",
     "speaking roles and background must be cast",
     lambda ctx: ctx["scenes"] >= 2 or "crowd/background" in ctx["signals"]),
]

# Script signal -> departments the dataset cannot staff.
NOT_IN_CORPUS = {
    "night lighting": [("Gaffer", "Electric", "night and twilight scenes need a lighting package"),
                       ("Key Grip", "Grip", "night work needs rigging and negative fill")],
    "stunts/safety": [("Stunt Coordinator", "Stunts", "scripted fights, falls or weapons"),
                      ("Armorer", "Props", "any weapon on set is a licensed, supervised item")],
    "special effects": [("SFX Supervisor", "Special Effects", "practical rain, smoke, fire or blood")],
    "vehicle": [("Picture Car Coordinator", "Transport", "vehicles that appear on camera")],
    "animals": [("Animal Wrangler", "Animals", "licensed handling and welfare supervision")],
    "music/playback": [("Music Supervisor", "Music", "on-camera music needs cleared rights and playback")],
    "crowd/background": [("2nd Assistant Director", "Direction", "background casting and crowd control")],
    "weather cover": [("Location Manager", "Locations", "exterior permits, access and weather cover")],
}
ALWAYS_UNSTAFFABLE = [
    ("1st Assistant Director", "Direction", "runs the shooting schedule on the floor"),
    ("Production Sound Mixer", "Sound", "every scene with dialogue is recorded live"),
]


def _signal_scenes(scenes: list[Scene]) -> dict[str, list[int]]:
    """Which scene numbers raised each requirement signal."""
    out: dict[str, list[int]] = {}
    for scene in scenes:
        for requirement in scene.requirements:
            out.setdefault(requirement, []).append(scene.number)
    return out


def derive_roles(scenes: list[Scene]) -> list[RoleRequirement]:
    signals = _signal_scenes(scenes)
    all_scene_numbers = [s.number for s in scenes]
    ctx = {
        "locations": len({s.location for s in scenes}),
        "scenes": len(scenes),
        "signals": set(signals),
    }
    roles: list[RoleRequirement] = []

    for category, display, department, reason in CORE:
        roles.append(RoleRequirement(
            role=display, category=category, department=department, priority="core",
            reason=reason, scene_numbers=all_scene_numbers,
            in_corpus=True, staffable=True))

    for category, display, department, reason, predicate in CONDITIONAL:
        if not predicate(ctx):
            continue
        roles.append(RoleRequirement(
            role=display, category=category, department=department, priority="recommended",
            reason=f"{ctx['locations']} {reason}" if category == "production_designer" else reason,
            scene_numbers=all_scene_numbers, in_corpus=True, staffable=True))

    # The writer is not staffed: a screenplay already exists, so the role is filled.
    roles.append(RoleRequirement(
        role="Writer", category="writer", department="Story", priority="attached",
        reason="A screenplay was supplied, so this role is already filled.",
        scene_numbers=[], in_corpus=True, staffable=False))

    for signal, entries in sorted(signals.items()):
        for display, department, reason in NOT_IN_CORPUS.get(signal, []):
            roles.append(RoleRequirement(
                role=display, category=None, department=department, priority="required",
                reason=f"{reason} (scene {', '.join(map(str, entries[:6]))})",
                scene_numbers=entries, in_corpus=False, staffable=False))

    for display, department, reason in ALWAYS_UNSTAFFABLE:
        roles.append(RoleRequirement(
            role=display, category=None, department=department, priority="required",
            reason=reason, scene_numbers=all_scene_numbers,
            in_corpus=False, staffable=False))

    return roles


def infer_brief(screenplay: str, scenes: list[Scene]) -> ProductionBrief:
    """Genres and tone from the screenplay itself, so crew search inherits them.

    Deterministic by design: the same script always yields the same brief, which
    is what makes the crew shortlist reproducible on stage.
    """
    text = screenplay.lower()
    hits: list[tuple[int, str]] = []
    for genre, words in GENRE_SYNONYMS.items():
        count = sum(len(re.findall(rf"\b{re.escape(w)}\b", text)) for w in words)
        if count:
            hits.append((count, genre))

    signals = {r for s in scenes for r in s.requirements}
    night = sum(s.time_of_day in {"NIGHT", "DAWN", "DUSK"} for s in scenes)
    # Scene composition is a stronger genre signal than vocabulary: a script that
    # is mostly night exteriors with weapons is a thriller whatever words it uses.
    if "stunts/safety" in signals:
        hits.append((2, "Thriller"))
    if night and night >= max(1, len(scenes) // 2):
        hits.append((1, "Thriller"))
    if not hits:
        hits.append((1, "Drama"))

    ranked: dict[str, int] = {}
    for count, genre in hits:
        ranked[genre] = ranked.get(genre, 0) + count
    genres = [g for g, _ in sorted(ranked.items(), key=lambda kv: (-kv[1], kv[0]))][:3]

    tone_bits = []
    if night:
        tone_bits.append(f"{night} of {len(scenes)} scenes shoot at night or twilight")
    exteriors = sum(s.interior_exterior != "INT" for s in scenes)
    if exteriors:
        tone_bits.append(f"{exteriors} exterior")
    if "stunts/safety" in signals:
        tone_bits.append("scripted action")

    return ProductionBrief(
        genres=genres,
        tone="; ".join(tone_bits) or "interior, dialogue-led",
        scene_count=len(scenes),
        location_count=len({s.location for s in scenes}),
        source="scene-composition + screenplay vocabulary",
    )
