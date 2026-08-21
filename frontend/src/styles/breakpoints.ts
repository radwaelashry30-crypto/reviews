/**
 * Mirrors the pixel breakpoints used throughout tokens.css / ui-kit.css.
 * CSS media queries can't read custom properties, so this file is the
 * source of truth for any JS that needs to branch on viewport width
 * (e.g. a `useMediaQuery` hook) -- keep it in sync with tokens.css by hand.
 */
export const BREAKPOINTS = {
  sm: 480,
  md: 768,
  lg: 1024,
  xl: 1280,
} as const;

export type BreakpointKey = keyof typeof BREAKPOINTS;
