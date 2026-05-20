// In-game era year conversion — see Guides/FAMILY_TREE_GUIDE.md §5.
//
//   Fourth Age:  year > 4033        → year - 4033
//   Third Age:   592 < year ≤ 4033  → year - 592
//   Earlier:     year ≤ 592         → "" (falls through)
//
// The raw simulation year is an absolute calendar value in the mod's timeline;
// these formulas map it to the displayed in-game era year.

export function toInGameYear(year) {
  const y = parseInt(year, 10);
  if (!Number.isFinite(y)) return '';
  if (y > 4033) return String(y - 4033);
  if (y > 592) return String(y - 592);
  return '';
}

// Same conversion, but prefixed with the era ("F.A." / "T.A.") for readability
// in places where the bare number alone would be ambiguous (e.g. year inputs).
export function toInGameYearLabel(year) {
  const y = parseInt(year, 10);
  if (!Number.isFinite(y)) return '';
  if (y > 4033) return `F.A. ${y - 4033}`;
  if (y > 592) return `T.A. ${y - 592}`;
  return '';
}
