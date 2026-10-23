/** 0 -> A, 25 -> Z, 26 -> AA, 51 -> AZ, 52 -> BA (spreadsheet-column style). */
export function letter(i: number): string {
  let s = '';
  let n = i + 1;
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}
