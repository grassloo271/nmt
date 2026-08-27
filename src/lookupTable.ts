/**
 * Loads the precomputed design-sweep results and interpolates
 * between grid points for whatever exact slider values the user
 * has selected. Replaces the fetch() call to the Python backend.
 *
 * Usage in App.tsx:
 *
 *   import { lookupAircraft } from "./lookupTable";
 *   const result = lookupAircraft(S, AR, margin);
 *
 * Put lookup_table.json in src/assets/ (or wherever you keep
 * static assets) and adjust the import path below.
 */

import lookupData from "./lookup_table_wmass.json";

// ============================================================
// TYPES
// ============================================================

type Axes = {
  S: number[];
  AR: number[];
  margin: number[];
};

type LookupFile = {
  axes: Axes;
  results: Record<string, any>;
};

const data = lookupData as LookupFile;

// ============================================================
// HELPERS
// ============================================================

/**
 * Finds the two grid indices in `axis` that bracket `value`,
 * plus how far between them `value` sits (0 = at lower, 1 = at
 * upper). Clamps to the grid edges if value is out of range.
 */
function bracket(
  axis: number[],
  value: number
): { lo: number; hi: number; t: number } {
  if (value <= axis[0]) {
    return { lo: 0, hi: 0, t: 0 };
  }

  if (value >= axis[axis.length - 1]) {
    const last = axis.length - 1;
    return { lo: last, hi: last, t: 0 };
  }

  for (let i = 0; i < axis.length - 1; i++) {
    if (value >= axis[i] && value <= axis[i + 1]) {
      const span = axis[i + 1] - axis[i];
      const t = span === 0 ? 0 : (value - axis[i]) / span;
      return { lo: i, hi: i + 1, t };
    }
  }

  // Shouldn't happen, but fall back to the last index.
  const last = axis.length - 1;
  return { lo: last, hi: last, t: 0 };
}

function keyFor(S: number, AR: number, margin: number): string {
  return `${S.toFixed(4)}_${AR.toFixed(4)}_${margin.toFixed(4)}`;
}

/**
 * Recursively interpolates two result objects that share the
 * same shape. Numbers are blended by `t`; everything else
 * (strings, booleans, arrays like violations) is taken from
 * whichever side is closer, since those aren't meaningfully
 * "between" two values.
 */
function blend(a: any, b: any, t: number): any {
  if (typeof a === "number" && typeof b === "number") {
    if (!Number.isFinite(a) || !Number.isFinite(b)) {
      return t < 0.5 ? a : b;
    }
    return a + (b - a) * t;
  }

  if (a === null || b === null) {
    return t < 0.5 ? a : b;
  }

  if (Array.isArray(a) || Array.isArray(b)) {
    return t < 0.5 ? a : b;
  }

  if (typeof a === "object" && typeof b === "object") {
    const out: Record<string, any> = {};
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    keys.forEach((k) => {
      out[k] = blend(a[k], b[k], t);
    });
    return out;
  }

  // strings, booleans, mismatched types -> nearest
  return t < 0.5 ? a : b;
}

function getEntry(S: number, AR: number, margin: number): any {
  const key = keyFor(S, AR, margin);
  const entry = data.results[key];

  if (!entry) {
    throw new Error(
      `No precomputed entry for S=${S}, AR=${AR}, margin=${margin}. ` +
        `This point isn't on the sweep grid.`
    );
  }

  return entry;
}

// ============================================================
// MAIN LOOKUP
// ============================================================

/**
 * Trilinear interpolation across the S / AR / margin grid.
 * Returns the same shape optimize_aircraft() used to return
 * from the backend, so it's a drop-in replacement for the
 * fetch() response.
 */
export function lookupAircraft(
  S: number,
  AR: number,
  margin: number
): any {
  const bS = bracket(data.axes.S, S);
  const bAR = bracket(data.axes.AR, AR);
  const bM = bracket(data.axes.margin, margin);

  // The 8 corners of the surrounding grid cell (some may
  // collapse to the same point if a value is at/near an edge).
  const corners: Record<string, any> = {};

  [bS.lo, bS.hi].forEach((si) => {
    [bAR.lo, bAR.hi].forEach((ai) => {
      [bM.lo, bM.hi].forEach((mi) => {
        const S_v = data.axes.S[si];
        const AR_v = data.axes.AR[ai];
        const M_v = data.axes.margin[mi];
        const cornerKey = `${si}_${ai}_${mi}`;
        corners[cornerKey] = getEntry(S_v, AR_v, M_v);
      });
    });
  });

  // Interpolate along margin first, then AR, then S.
  const alongMargin: Record<string, any> = {};
  [bS.lo, bS.hi].forEach((si) => {
    [bAR.lo, bAR.hi].forEach((ai) => {
      const lo = corners[`${si}_${ai}_${bM.lo}`];
      const hi = corners[`${si}_${ai}_${bM.hi}`];
      alongMargin[`${si}_${ai}`] = blend(lo, hi, bM.t);
    });
  });

  const alongAR: Record<string, any> = {};
  [bS.lo, bS.hi].forEach((si) => {
    const lo = alongMargin[`${si}_${bAR.lo}`];
    const hi = alongMargin[`${si}_${bAR.hi}`];
    alongAR[`${si}`] = blend(lo, hi, bAR.t);
  });

  const final = blend(alongAR[`${bS.lo}`], alongAR[`${bS.hi}`], bS.t);

  return final;
}

// ============================================================
// GRID BOUNDS (handy for clamping slider min/max to match)
// ============================================================

export const gridBounds = {
  S: { min: data.axes.S[0], max: data.axes.S[data.axes.S.length - 1] },
  AR: { min: data.axes.AR[0], max: data.axes.AR[data.axes.AR.length - 1] },
  margin: {
    min: data.axes.margin[0],
    max: data.axes.margin[data.axes.margin.length - 1],
  },
};