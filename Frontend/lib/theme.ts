/**
 * Design tokens for the JARVIS DevPilot mobile app.
 * Dark-mode-first theme matching the cyberpunk/terminal aesthetic.
 */

export const Colors = {
  // Backgrounds
  background: '#0d1117',
  surface: '#161b22',
  card: '#1c2128',
  cardLight: '#21262d',

  // Borders
  border: '#30363d',
  borderLight: '#444c56',

  // Brand / Primary
  primary: '#58a6ff',
  primaryBg: '#0d2236',
  primaryDark: '#1f6feb',
  primaryLight: '#a5d6ff',

  // Text
  foreground: '#e6edf3',
  muted: '#8b949e',
  mutedDark: '#484f58',

  // Semantic Colors
  green: '#3fb950',
  greenBg: '#0e2e14',
  greenLight: '#56d364',

  red: '#f85149',
  redBg: '#2d0f0f',
  redBorder: '#6e2525',
  redLight: '#ffa198',

  yellow: '#d29922',
  yellowBg: '#2d1f00',
  yellowLight: '#e3b341',

  purple: '#bc8cff',
  purpleBg: '#1b1038',

  cyan: '#39c5cf',
  orange: '#f0883e',

  // Input
  input: '#21262d',
} as const;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const FontSize = {
  xs: 11,
  sm: 13,
  md: 15,
  lg: 17,
  xl: 20,
  xxl: 24,
} as const;

export const BorderRadius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  full: 9999,
} as const;
