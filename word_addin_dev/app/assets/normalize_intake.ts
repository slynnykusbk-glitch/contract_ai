const ZERO_WIDTH_REGEX = /[\u200B-\u200F\u2060-\u2064\uFEFF]/g;
const NBSP_REGEX = /\u00A0/g;
const MULTI_SPACE_REGEX = /[ \t]+/g;
const DASH_REGEX = /[\u2010-\u2015\u2212]/g;
const DOUBLE_QUOTE_REGEX = /[\u00AB\u00BB\u201C-\u201F\u2033\u2036]/g;
const SINGLE_QUOTE_REGEX = /[\u2018-\u201B\u2032\u2035]/g;

const dashMap: Record<string, string> = {
  '\u2010': '-',
  '\u2011': '-',
  '\u2012': '-',
  '\u2013': '-',
  '\u2014': '-',
  '\u2015': '-',
  '\u2212': '-',
};

const doubleQuoteMap: Record<string, string> = {
  '\u201C': '"',
  '\u201D': '"',
  '\u201E': '"',
  '\u201F': '"',
  '\u00AB': '"',
  '\u00BB': '"',
  '\u2033': '"',
  '\u2036': '"',
};

const singleQuoteMap: Record<string, string> = {
  '\u2018': "'",
  '\u2019': "'",
  '\u201A': "'",
  '\u201B': "'",
  '\u2032': "'",
  '\u2035': "'",
};

function replaceFromMap(source: string, re: RegExp, map: Record<string, string>): string {
  return source.replace(re, ch => map[ch] ?? ch);
}

export function normalizeIntakeText(input: string): string {
  if (!input) return '';
  let text = input.normalize('NFC');
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  text = text.replace(ZERO_WIDTH_REGEX, '');
  text = text.replace(NBSP_REGEX, ' ');
  text = replaceFromMap(text, DASH_REGEX, dashMap);
  text = replaceFromMap(text, DOUBLE_QUOTE_REGEX, doubleQuoteMap);
  text = replaceFromMap(text, SINGLE_QUOTE_REGEX, singleQuoteMap);
  text = text.replace(MULTI_SPACE_REGEX, ' ');
  return text.trim();
}
