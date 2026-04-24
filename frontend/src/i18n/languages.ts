export interface LanguageInfo {
  code: string;
  nativeLabel: string;
  englishLabel: string;
  scriptRegex?: RegExp;
}

export const LANGUAGES: LanguageInfo[] = [
  { code: 'hi-IN', nativeLabel: 'हिन्दी', englishLabel: 'Hindi', scriptRegex: /[\u0900-\u097F]/ },
  { code: 'mr-IN', nativeLabel: 'मराठी', englishLabel: 'Marathi', scriptRegex: /[\u0900-\u097F]/ },
  { code: 'gu-IN', nativeLabel: 'ગુજરાતી', englishLabel: 'Gujarati', scriptRegex: /[\u0A80-\u0AFF]/ },
  { code: 'kn-IN', nativeLabel: 'ಕನ್ನಡ', englishLabel: 'Kannada', scriptRegex: /[\u0C80-\u0CFF]/ },
  { code: 'ta-IN', nativeLabel: 'தமிழ்', englishLabel: 'Tamil', scriptRegex: /[\u0B80-\u0BFF]/ },
  { code: 'te-IN', nativeLabel: 'తెలుగు', englishLabel: 'Telugu', scriptRegex: /[\u0C00-\u0C7F]/ },
  { code: 'ml-IN', nativeLabel: 'മലയാളം', englishLabel: 'Malayalam', scriptRegex: /[\u0D00-\u0D7F]/ },
  { code: 'bn-IN', nativeLabel: 'বাংলা', englishLabel: 'Bengali', scriptRegex: /[\u0980-\u09FF]/ },
  { code: 'en-IN', nativeLabel: 'English', englishLabel: 'English' },
];

export const LANGUAGE_BY_CODE: Record<string, LanguageInfo> = Object.fromEntries(
  LANGUAGES.map((l) => [l.code, l]),
);

export function detectLanguageFromText(text: string, fallback: string): string {
  if (!text) return fallback;
  for (const l of LANGUAGES) {
    if (l.scriptRegex && l.scriptRegex.test(text)) return l.code;
  }
  return fallback;
}
