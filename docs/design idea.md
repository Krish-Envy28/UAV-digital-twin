# Design System Brief — Sci-Fi Command Dashboard Aesthetic

## Mood keywords
Mission control, HUD, futuristic telemetry, glass-panel overlay, cinematic space photography backdrop, precise/technical, dark-mode-only.

## Color palette

| Role | Value | Usage |
|---|---|---|
| Base background | `#0B0D12` – `#0F1116` | Near-black, slightly cool-toned |
| Panel surface | `rgba(255,255,255,0.04–0.06)` on dark, with `backdrop-filter: blur(20px)` | Glass panels over imagery |
| Panel border | `rgba(255,255,255,0.08–0.12)` 1px | Barely-there separation, not a hard line |
| Primary accent | `#FF6B35` (orange) | CTAs, active nav state, highlight numbers, chart fill |
| Secondary accent | `#3B82F6`-ish blue, used sparingly | Secondary data series, occasional icon |
| Text primary | `#F5F5F7` / near-white | Headings, key numbers |
| Text secondary | `rgba(255,255,255,0.5–0.6)` gray | Labels, captions |
| Success/status | Muted green, low saturation | Small status dots only |

## Typography

- Headings: clean geometric sans (Inter, Space Grotesk, or similar) — medium weight, tight letter-spacing
- Data/numbers/labels: a technical/mono-adjacent face (e.g. IBM Plex Mono, JetBrains Mono, or Inter with tabular-nums) for anything that looks like live telemetry (stat values, percentages)
- Scale: large hero number (32–40px) for hero stat, 12–13px uppercase tracked-out labels above each stat block

## Layout structure

- **Top bar:** logo/wordmark left, pill-shaped segmented nav control center (rounded-full container, active tab gets solid orange-tinted background), search + notification + avatar icons right
- **Full-bleed background:** dramatic photo/render fills the entire viewport behind everything, with a dark gradient overlay (bottom/edges darker) so panels stay legible
- **Left column:** stacked small stat/nav cards, icon + label, ~180px wide, generous vertical gap
- **Center:** the hero visual (the "product" — in your case, the engine) sits large and mostly unobstructed, panels float around it, not on top of it
- **Right column:** a summary/detail panel (image thumbnail + spec rows + a primary CTA button), plus smaller stacked utility cards below
- **Bottom row:** wide data-viz cards side by side (radar/spider chart on one, horizontal progress bars on another) — this is where "live system status" personality lives

## Component styling

- Corner radius: consistently 14–18px on cards, fully rounded (999px) on nav pills and buttons
- Glass panels: subtle blur + low-opacity fill + 1px near-invisible border, NOT drop-shadow-heavy — depth comes from blur/contrast against the photo behind it, not shadows
- Buttons: solid orange fill for primary action, ghost/outline for secondary, fully rounded
- Progress bars: thin (4–6px), rounded caps, orange or blue fill on a `rgba(255,255,255,0.08)` track
- Radar/spider chart: single orange fill at low opacity with a solid orange outline stroke, thin gridlines at low opacity

## Iconography
Thin (1.5px stroke) line icons only — no filled icons, no duotone. Lucide or Phosphor (thin variant) match this style closely.

## Motion cues implied by this design (for later, not just static)
- Numbers that look "live" should count up/tick on load, not just appear
- Progress bars should animate fill from 0 → value on load
- Hover on nav pills / cards: subtle background brighten + border lightens, no heavy scale/shadow

## Note on how this pairs with the engine content
This dashboard shell is the "instrument panel" — the exploded-view engine visual becomes the hero centerpiece the panels float around, not a separate section. Keep the engine graphic's line-art style visually distinct from the UI chrome (UI = solid glass panels, engine = linework) so they read as content vs. interface, not as one flattened image.
