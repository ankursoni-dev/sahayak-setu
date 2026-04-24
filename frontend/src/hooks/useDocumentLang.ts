import { useEffect } from 'react';
import { useAppStore } from '@/store/appStore';

/** Syncs <html lang="..."> with the selected language so screen readers pronounce correctly. */
export function useDocumentLang(): void {
  const language = useAppStore((s) => s.selectedLanguage);
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = language;
    }
  }, [language]);
}
