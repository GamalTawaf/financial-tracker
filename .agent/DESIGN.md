# DESIGN.md

Design contract for Financial Tracker (product name in UI: **Ledger**).
Tokens live only in `frontend/src/app.css`. Do not invent a palette in components.

Polish method: [unslop](https://github.com/heydamir/unslop) by Damir Sokolovsky, CC BY 4.0.

## Direction

- **Product:** Personal receipt expense tracker for item-level Ontario spend.
- **Character:** calm, exact, ledger-warm.
- **World:** paper slips, grocery ink, cool kitchen light — warm paper neutrals; green only as accent.
- **Moments:** category spend bars; tabular money columns.
- **Signature:** hairline ledger rules + amber review chip with status dot.

## Mode

Operate — scanability and precision over marketing spectacle. Quiet chrome; richness in content.

## Tokens (host)

| Token | Role |
| --- | --- |
| `--color-brand` / `-light` / `-dark` | Accent + button lighting |
| `--color-ink` / `-secondary` / `-muted` | Text ramp |
| `--color-surface` / `-raised` / `-sunken` | Page / panel / track |
| `--color-border` / `-strong` | Hairlines |
| `--color-danger` / `-soft`, success, warning | Semantics |
| `--font-sans` / `--font-display` | Source Sans 3 / Fraunces |
| `--radius-sm` / `--radius-md` | 8 / 14 |
| `--shadow-button` / `--shadow-panel` | Depth |
| `--focus-ring` | Single brand focus (no second hue) |

Values: brand `#1F6B4A` · surfaces `#F0EEE9` / `#FAF9F6` · ink `#1A1C1A`.

## Button lighting (reel DeeuCXtNkjL)

One global `Button`: gradient rest, inset light/shade, small outer drop; hover brighter top; press `translateY(1px)` only; ghost has insets, no outer drop; no primary fill on legal/ghost links.

## Bans

No Popover split buttons; no oversized fields; no second-hue focus; no 24/12 card lift; no press-scale; no spinner→check; no purple/glow/emoji chrome; no gitleaks/knip/jscpd/osv-scanner/lefthook unless asked.
