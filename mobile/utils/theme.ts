/**
 * Design tokens: one source of truth for color, type, space and motion.
 *
 * World: "the ledger" (see DESIGN.md). Warm paper, ink accents, hairline rules,
 * serif numerals. Every screen composes these tokens instead of raw values.
 */

export const Colors = {
  // Surfaces
  paper: '#F2F0E9',
  surface: '#FBFAF5',
  surfaceAlt: '#EBE8DE',
  line: '#DAD5C7',
  lineStrong: '#C9C2B0',

  // Ink
  ink: '#171A16',
  inkSoft: '#565A52',
  inkMuted: '#64685E',
  onInk: '#F7F5EE',

  // Money semantics
  income: '#1B6B4C',
  expense: '#A33A2A',
  investment: '#8A6516',
  debt: '#2A5A72',
  receivable: '#6A4A85',
  danger: '#A32B2B',

  // Tints (semantic color at ~10% over paper)
  incomeTint: 'rgba(27, 107, 76, 0.10)',
  expenseTint: 'rgba(163, 58, 42, 0.10)',
  investmentTint: 'rgba(138, 101, 22, 0.10)',
  debtTint: 'rgba(42, 90, 114, 0.10)',
  receivableTint: 'rgba(106, 74, 133, 0.10)',
  dangerTint: 'rgba(163, 43, 43, 0.10)',
  inkTint: 'rgba(23, 26, 22, 0.06)',

  // Scrim behind sheets
  scrim: 'rgba(23, 26, 22, 0.45)',
} as const;

export const Space = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
  gutter: 20,
} as const;

export const Radius = {
  control: 6,
  block: 10,
  sheet: 16,
  pill: 999,
} as const;

export const Fonts = {
  /** Display serif: screen titles and hero amounts. */
  serif: 'InstrumentSerif',
  regular: 'PlexRegular',
  medium: 'PlexMedium',
  semibold: 'PlexSemiBold',
} as const;

/**
 * Type styles. Custom static faces carry their weight in the file, so styles
 * set `fontFamily` and never `fontWeight`.
 */
export const Type = {
  hero: {
    fontFamily: Fonts.serif,
    fontSize: 44,
    lineHeight: 48,
    letterSpacing: -0.6,
    color: Colors.ink,
  },
  h1: {
    fontFamily: Fonts.serif,
    fontSize: 34,
    lineHeight: 38,
    letterSpacing: -0.4,
    color: Colors.ink,
  },
  h2: {
    fontFamily: Fonts.serif,
    fontSize: 26,
    lineHeight: 31,
    letterSpacing: -0.2,
    color: Colors.ink,
  },
  h3: {
    fontFamily: Fonts.medium,
    fontSize: 20,
    lineHeight: 26,
    color: Colors.ink,
  },
  title: {
    fontFamily: Fonts.semibold,
    fontSize: 17,
    lineHeight: 23,
    color: Colors.ink,
  },
  bodyStrong: {
    fontFamily: Fonts.medium,
    fontSize: 15,
    lineHeight: 21,
    color: Colors.ink,
  },
  body: {
    fontFamily: Fonts.regular,
    fontSize: 14,
    lineHeight: 21,
    color: Colors.ink,
  },
  caption: {
    fontFamily: Fonts.regular,
    fontSize: 12,
    lineHeight: 17,
    color: Colors.inkMuted,
  },
  micro: {
    fontFamily: Fonts.medium,
    fontSize: 11,
    lineHeight: 15,
    letterSpacing: 0.08,
    color: Colors.inkMuted,
  },
  /** Money in lists and tables: fixed-width digits, right aligned. */
  amount: {
    fontFamily: Fonts.semibold,
    fontSize: 15,
    lineHeight: 20,
    color: Colors.ink,
  },
  amountLarge: {
    fontFamily: Fonts.semibold,
    fontSize: 17,
    lineHeight: 22,
    color: Colors.ink,
  },
} as const;

export const Shadow = {
  none: {},
  hairline: {
    borderWidth: 1,
    borderColor: Colors.line,
  },
  raised: {
    borderWidth: 1,
    borderColor: Colors.line,
    shadowColor: 'rgba(23, 26, 22, 0.85)',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
    elevation: 1,
  },
  sheet: {
    shadowColor: 'rgba(23, 26, 22, 0.9)',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.16,
    shadowRadius: 16,
    elevation: 12,
  },
} as const;

export const Motion = {
  fast: 150,
  base: 220,
  slow: 320,
} as const;