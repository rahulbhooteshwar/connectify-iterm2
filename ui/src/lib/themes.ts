/** Tile themes. The ids are what hosts.json stores and what the backend
 * validates (HOST_THEMES in main.py) - the two lists must match, and there is
 * a test on the Python side that checks this file against it. */

export interface TileTheme {
  id: string
  label: string
  /** the accent - dot, tile edge, glow */
  color: string
  /** a softer companion for backgrounds/rings in either mode */
  soft: string
  /** the same hue with more presence - the hover wash across a whole tile */
  strong: string
}

export const TILE_THEMES: TileTheme[] = [
  { id: 'default', label: 'Neutral', color: '#94a3b8', soft: 'rgba(148,163,184,0.16)', strong: 'rgba(148,163,184,0.30)' },
  { id: 'red',     label: 'Red',     color: '#f87171', soft: 'rgba(248,113,113,0.16)', strong: 'rgba(248,113,113,0.30)' },
  { id: 'orange',  label: 'Orange',  color: '#fb923c', soft: 'rgba(251,146,60,0.16)', strong: 'rgba(251,146,60,0.30)' },
  { id: 'amber',   label: 'Amber',   color: '#fbbf24', soft: 'rgba(251,191,36,0.16)', strong: 'rgba(251,191,36,0.30)' },
  { id: 'green',   label: 'Green',   color: '#34d399', soft: 'rgba(52,211,153,0.16)', strong: 'rgba(52,211,153,0.30)' },
  { id: 'teal',    label: 'Teal',    color: '#2dd4bf', soft: 'rgba(45,212,191,0.16)', strong: 'rgba(45,212,191,0.30)' },
  { id: 'blue',    label: 'Blue',    color: '#60a5fa', soft: 'rgba(96,165,250,0.16)', strong: 'rgba(96,165,250,0.30)' },
  { id: 'violet',  label: 'Violet',  color: '#a78bfa', soft: 'rgba(167,139,250,0.16)', strong: 'rgba(167,139,250,0.30)' },
  { id: 'pink',    label: 'Pink',    color: '#f472b6', soft: 'rgba(244,114,182,0.16)', strong: 'rgba(244,114,182,0.30)' },
]

export function themeById(id: string | undefined): TileTheme {
  return TILE_THEMES.find((t) => t.id === id) ?? TILE_THEMES[0]
}
