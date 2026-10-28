# Design

## World: the ledger

A personal cash book, not a dashboard. Warm paper, ink, hairline rules, and
numbers set like a printed ledger. Cards are the exception, not the layout: rows
are separated by rules, amounts sit in a right-aligned numeric column, and the
hero figure on each screen is set in a display serif.

Deliberately not: dark neon fintech, glassmorphism, gradient text, emoji icons,
uniform rounded card stacks, cream + terracotta.

## Palette

| Token | Value | Use |
|---|---|---|
| `paper` | `#F2F0E9` | app background |
| `surface` | `#FBFAF5` | sheets, inputs, raised blocks |
| `surfaceAlt` | `#EBE8DE` | inset blocks, progress tracks |
| `line` | `#DAD5C7` | hairlines, borders |
| `ink` | `#171A16` | primary text, primary buttons |
| `inkSoft` | `#565A52` | secondary text |
| `inkMuted` | `#64685E` | captions, metadata (>=4.5:1 on paper) |
| `income` | `#1B6B4C` | income, positive net |
| `expense` | `#A33A2A` | expense, overdue |
| `investment` | `#8A6516` | investment |
| `debt` | `#2A5A72` | hutang |
| `receivable` | `#6A4A85` | piutang |
| `danger` | `#A32B2B` | destructive actions |

One accent: ink. Semantic colors only for money types and status, never for
chrome. Tints are the semantic color at 10-12% alpha on `surface`.

## Type

- Display: **Instrument Serif** (400). Screen titles, hero amounts.
- UI: **IBM Plex Sans** (400 / 500 / 600). Everything else.
- Amounts: Plex 600 with `fontVariant: ['tabular-nums']`, right aligned.

Scale: 11 micro · 12 caption · 14 body · 15 bodyStrong · 17 title · 20 h3 ·
26 h2 · 34 h1 · 44 hero. Line height 1.2-1.45. Letter spacing negative only at
26px and above.

## Space and shape

4/8 rhythm: 4, 8, 12, 16, 24, 32, 48. Screen gutter 20. Radii: 6 (control),
10 (block), 16 (sheet), 999 (chip). Hairline 1px `line`.

## Composition rules

- Lists use hairline separators, not per-row cards.
- Section header: 12px uppercase-free Plex 600 `ink`, optional right-side action
  in `inkMuted`; no decorative eyebrows above every block.
- Hero block: label in 11px muted uppercase with 0.08 tracking, amount in
  Instrument Serif, semantic split row under a hairline.
- Empty state: one line of cause + one action. No emoji.
- Icons: Ionicons outline, 16-22px, `inkSoft`; semantic tint only inside a tint
  circle.

## Motion

150-240ms, ease-out. Screen content fades up 8px on mount once. Sheets slide
from the bottom with a drag handle. Pressed controls scale to 0.98, no layout
shift. `AccessibilityInfo.isReduceMotionEnabled` disables all of it.

## Accessibility floor

Touch targets >= 44x44 with >= 8px gaps. Text contrast >= 4.5:1 (`inkMuted` is
the floor, checked). Every icon-only control has `accessibilityLabel`, every
async control exposes `accessibilityState={{ busy }}`, filter tabs expose
`role="tab"` + `selected`. Numbers never rely on color alone: sign and label
carry the meaning.