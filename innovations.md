# Dashboard Content Spec — Mapping the 5 Innovations to the Vortex Layout

Reference layout recap: top pill nav, left stat stack, center hero visual, right detail panel, bottom two data-viz cards. Below is what replaces each region.

## Top nav (pill segmented control)
`Overview | Telemetry | Mission | What-If | Recommendation` — five tabs, one per innovation area, "Overview" as the landing/active state.

## Left column — small stat cards (Innovation 1 + 4 outputs)
Icon + label + big number, same visual weight as the reference's Defense/Energy/Cargo cards:
- **Health Index** — e.g. `78%`
- **Degradation Trend** — trajectory stage label (`Progressive Degradation`) not just a number, since Innovation 4 explicitly says don't reduce this to a static %
- **RUL** — `140 min`, with a small secondary label "mission-conditioned" so it doesn't read as an isolated figure (this directly reflects your Innovation 1 note)
- **Confidence** — the AI PHM confidence score

## Center — hero visual
The engine (exploded-view line art) stays the centerpiece, same role the spaceship plays in the reference. Optionally: a subtle color-coded glow/outline around the engine matching the current recommendation state (green/yellow/orange/red) so the hero visual itself communicates status at a glance, not just the text panel.

## Right panel — "Mission Overview" (Innovation 1 + 2)
Same slot as the reference's ship-stats card:
- Rows: **Mission Duration**, **Altitude**, **Load/Throttle** — the three mission parameters that feed Mission Risk
- A prominent **Mission Risk** badge (HIGH / MODERATE / LOW), colored
- Primary CTA button below, but instead of a generic action button, this is the **Operational Recommendation**: `🟢 CONTINUE MISSION` / `🟡 MONITOR CLOSELY` / `🟠 REDUCE LOAD` / `🔴 RETURN TO BASE` / `🔧 MAINTENANCE REQUIRED`, in the same solid-orange-CTA visual weight as the reference

## Bottom-left — radar/spider chart (Innovation 1, repurposed from "Ship Performance")
Axes: Health, RUL (normalized), Confidence, Degradation Stability, Mission Fit. This gives the "system vitals at a glance" read the reference's radar chart has, but scoped to engine+mission fitness rather than generic ship stats.

## Bottom-right — swap the reference's "Weapons Range / Energy System" bars for two things (Innovation 3 + 5)

**Option A — What-If Comparison table** (matches your own sketch exactly):
```
                 ORIGINAL    ALTERNATIVE
Duration           120 min       90 min
Altitude           6000 m       4000 m
Load                 90%          70%
Risk                 HIGH          LOW
Recommendation      MODIFY        ACCEPT
```
Rendered as two side-by-side stat columns, not bars — this is a comparison table, not a progress-bar metric, so don't force it into the reference's bar-chart component.

**Option B — Degradation Trajectory bar** (Innovation 4): a horizontal 5-stage progress track — Healthy → Early Deviation → Incipient → Progressive Degradation → Critical — with the current stage highlighted in orange and stages past it dimmed, functioning like a "how far along this trajectory are we" strip rather than a percentage bar.

If space allows both, stack them; if only one bottom-right slot, What-If is the stronger showcase of Innovation 3 for a pitch/demo context — visually novel and directly explains "the system doesn't just predict, it recommends."

## One integration note for Antigravity
Innovation 5's explainability requirement ("Reason: Predicted degradation combined with high mission load and duration results in elevated mission risk") needs a small text line under the Recommendation CTA, not just the badge — the reasoning sentence is part of the innovation, not an optional tooltip. Don't let the UI reduce it to just a colored badge with no explanation text.
