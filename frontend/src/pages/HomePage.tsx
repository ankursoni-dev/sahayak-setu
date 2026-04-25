import { useCallback, useState } from 'react';
import { Header } from '@/components/shared/Header';
import { Footer } from '@/components/shared/Footer';
import { BackgroundDecor } from '@/components/BackgroundDecor';
import { SearchInput } from '@/components/SearchInput';
import { VoiceInput } from '@/components/VoiceInput';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { ModeTabs, type Mode } from '@/components/ModeTabs';
import { ExampleChips } from '@/components/ExampleChips';
import { ConversationFeed } from '@/components/ConversationFeed';
import { LastQueryBanner } from '@/components/LastQueryBanner';
import { OutcomePrompt } from '@/components/OutcomePrompt';
import { EligibilityFinder } from '@/components/EligibilityFinder';
import { SchemesGrid } from '@/components/SchemesGrid';
import { SchemeSheet } from '@/components/SchemeSheet';
import { SidebarPanel } from '@/components/SidebarPanel';
import { DebugDrawer } from '@/components/DebugDrawer';
import { FeaturesSection } from '@/components/FeaturesSection';
import { useVoice } from '@/hooks/useVoice';
import { useSearch } from '@/hooks/useSearch';
import { useDocumentLang } from '@/hooks/useDocumentLang';
import { useAppStore } from '@/store/appStore';
import { stripCitationMarkers } from '@/lib/citations';
import type { CuratedScheme } from '@/data/curatedSchemes';

export default function HomePage() {
  useDocumentLang();
  const [mode, setMode] = useState<Mode>('talk');
  const [openScheme, setOpenScheme] = useState<CuratedScheme | null>(null);

  const { submitQuery } = useSearch();
  const selectedLanguage = useAppStore((s) => s.selectedLanguage);
  const voice = useVoice({
    onTranscript: (transcript) => {
      void submitQuery(transcript, {
        origin: 'voice',
        onAnswer: (payload) => {
          if (payload.answer && voice.transport !== 'vapi') {
            voice.speak(stripCitationMarkers(payload.answer), selectedLanguage);
          } else {
            useAppStore.getState().setStatus('Ready', 'green');
          }
        },
      });
    },
  });

  const handleTextSubmit = useCallback(
    (query: string) => {
      void submitQuery(query, {
        origin: 'text',
        onAnswer: (payload) => {
          // Text mode: no TTS — user can read. Just reset status.
          useAppStore.getState().setStatus('Ready', 'green');
          // Keep `voice` in deps but unused here — avoids stale-closure churn when
          // the user later switches transport mid-session.
          void payload;
        },
      });
    },
    [submitQuery],
  );

  const handleAskAboutScheme = useCallback(
    (scheme: CuratedScheme) => {
      setOpenScheme(null);
      void handleTextSubmit(`Tell me more about ${scheme.name} and how I can apply.`);
    },
    [handleTextSubmit],
  );

  const handleCheckEligibility = useCallback((scheme: CuratedScheme) => {
    setMode('finder');
    useAppStore.getState().setStatus(`Checking ${scheme.name}…`, 'orange');
    document.getElementById('interact')?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const handleVoiceToggle = useCallback(() => {
    if (voice.state === 'idle') voice.start();
    else voice.stop();
  }, [voice]);

  return (
    <div className="relative min-h-screen">
      <BackgroundDecor />
      <Header />

      <main className="relative z-10 mx-auto max-w-[1280px] px-6 pb-20 pt-16">
        <Hero />

        <section id="interact" className="mt-14 scroll-mt-20 grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="card-soft flex flex-col gap-5 p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <ModeTabs mode={mode} onChange={setMode} />
              <LanguageSwitcher />
            </div>

            {mode === 'talk' ? (
              <>
                <VoiceInput
                  active={voice.state === 'listening'}
                  dbLevel={voice.dbLevel}
                  liveCaption={voice.liveCaption}
                  onToggle={handleVoiceToggle}
                />
                <SearchInput onSubmit={handleTextSubmit} />
                <ExampleChips onPick={handleTextSubmit} />
              </>
            ) : (
              <EligibilityFinder
                onSubmit={(query) => {
                  setMode('talk');
                  handleTextSubmit(query);
                }}
              />
            )}

            <div id="conversation" className="scroll-mt-20">
              <OutcomePrompt />
              <LastQueryBanner onAskAgain={handleTextSubmit} />
              <div className="mt-4">
                <ConversationFeed />
              </div>
            </div>
          </div>

          <div className="lg:sticky lg:top-24 lg:self-start">
            <SidebarPanel />
          </div>
        </section>

        <FeaturesSection />

        <section id="schemes" className="mt-20 scroll-mt-20">
          <p className="eyebrow mb-3 text-center">Popular schemes</p>
          <h2 className="mb-10 text-center text-3xl sm:text-4xl">Commonly asked, directly linked.</h2>
          <SchemesGrid onOpen={setOpenScheme} onCheckEligibility={handleCheckEligibility} />
        </section>
      </main>

      <Footer />
      <SchemeSheet scheme={openScheme} onClose={() => setOpenScheme(null)} onAskAboutThis={handleAskAboutScheme} />
      <DebugDrawer />
    </div>
  );
}

function Hero() {
  return (
    <section className="relative z-10 flex flex-col items-center text-center">
      <p className="eyebrow mb-5">India's Multilingual Welfare AI</p>
      <h1 className="mx-auto max-w-3xl text-[2.75rem] leading-[1.05] sm:text-6xl">
        Every voice. <span className="italic text-[var(--color-saffron)]">Every language.</span>{' '}
        <br className="hidden sm:block" />
        One सेतु.
      </h1>
      <p className="mt-6 max-w-xl text-base text-[var(--color-ink-muted)]">
        Ask about Indian government schemes in your mother tongue. Instant, verified answers grounded in official
        sources.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <a href="#interact" className="btn-cta">
          Start speaking
        </a>
        <a href="#schemes" className="btn-outline">
          Browse schemes
        </a>
      </div>
    </section>
  );
}
