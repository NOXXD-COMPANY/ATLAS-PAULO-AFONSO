// Os dados do CNEFE vêm em caixa alta ("RUA SAO LUCAS, 190 B"). Na tela,
// caixa de título lê melhor; siglas e números romanos ficam como estão.

const CONECTIVOS = new Set(['de', 'da', 'do', 'das', 'dos', 'e', 'em', 'na', 'no', 'nas', 'nos', 'a', 'o']);
const ROMANO = /^(i{1,3}|iv|v|vi{1,3}|ix|x)$/;
const SEM_VOGAL = /^[^aeiouáàâãéêíóôõúü]+$/;

function formatWord(word: string, index: number): string {
  const lower = word.toLocaleLowerCase('pt-BR');
  const letters = lower.replace(/[^a-zà-ÿ]/g, '');
  if (!letters) return lower;
  if (ROMANO.test(letters) || (SEM_VOGAL.test(letters) && letters.length > 1)) return word.toLocaleUpperCase('pt-BR');
  if (index > 0 && CONECTIVOS.has(letters)) return lower;
  return lower.charAt(0).toLocaleUpperCase('pt-BR') + lower.slice(1);
}

export function titleCase(text: string | null | undefined): string {
  if (!text) return '';
  return text.trim().split(/\s+/).map(formatWord).join(' ');
}

export function formatNumber(n: number, digits = 0): string {
  return n.toLocaleString('pt-BR', { maximumFractionDigits: digits });
}

export function formatArea(m2: number | null | undefined): string | null {
  if (m2 == null || !Number.isFinite(m2) || m2 <= 0) return null;
  return m2 >= 10000 ? `${formatNumber(m2 / 10000, 2)} ha` : `${formatNumber(Math.round(m2))} m²`;
}
