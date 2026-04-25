import { useCallback, useEffect, useRef, useState } from 'react';
import Vapi from '@vapi-ai/web';
import { env } from '@/lib/env';
import { useAppStore } from '@/store/appStore';
import { detectLanguageFromText } from '@/i18n/languages';
import type { VoiceState, VoiceTransport } from '@/types/voice';

interface UseVoiceOptions {
  onTranscript: (text: string) => void;
}

interface UseVoiceReturn {
  state: VoiceState;
  transport: VoiceTransport;
  liveCaption: string;
  start: () => void;
  stop: () => void;
  speak: (text: string, language: string, onEnd?: () => void) => void;
  isSupported: boolean;
  dbLevel: number;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function resolveSpeechRecognition(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useVoice({ onTranscript }: UseVoiceOptions): UseVoiceReturn {
  const [state, setState] = useState<VoiceState>('idle');
  const [transport, setTransport] = useState<VoiceTransport>('none');
  const [liveCaption, setLiveCaption] = useState('');
  const [dbLevel, setDbLevel] = useState(0);

  const vapiRef = useRef<Vapi | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const meterRafRef = useRef<number | null>(null);
  const meterStreamRef = useRef<MediaStream | null>(null);
  /** When a Vapi call ends suspiciously fast with no transcript, treat the
   * assistant/key combo as broken for this tab session and route to browser. */
  const vapiBrokenRef = useRef(false);
  const vapiCallStartAtRef = useRef(0);
  const vapiGotTranscriptRef = useRef(false);
  /** Set by stop() so the call-end handler can tell user-initiated termination
   * apart from a Vapi-side failure. Without this, a user clicking Stop within
   * 3 seconds (before saying anything) trips the broken-flag heuristic and
   * permanently downgrades the session to browser STT. */
  const userInitiatedStopRef = useRef(false);
  /** Accumulate all final transcripts within a single Vapi call so the user can
   * pause mid-sentence. We submit once on call-end (Stop button or natural end). */
  const vapiAccumulatedRef = useRef('');

  const selectedLanguage = useAppStore((s) => s.selectedLanguage);
  const setVoice = useAppStore((s) => s.setVoice);
  const setStatus = useAppStore((s) => s.setStatus);

  /** Stash onTranscript in a ref so the long-lived Vapi listeners (registered once
   * on mount) always read the latest callback. Without this, an inline arrow on the
   * caller (e.g. <HomePage onTranscript={(t) => ...} />) creates a new function
   * every render and the init useEffect would either re-run constantly (causing
   * duplicate listeners) or close over a stale callback from the very first render. */
  const onTranscriptRef = useRef(onTranscript);
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  const SpeechRecognitionImpl = resolveSpeechRecognition();
  const isSupported = Boolean(SpeechRecognitionImpl) || Boolean(env.VAPI_PUBLIC_KEY);

  const teardownMeter = useCallback(() => {
    if (meterRafRef.current !== null) cancelAnimationFrame(meterRafRef.current);
    meterRafRef.current = null;
    meterStreamRef.current?.getTracks().forEach((t) => t.stop());
    meterStreamRef.current = null;
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      void audioCtxRef.current.close().catch(() => undefined);
    }
    audioCtxRef.current = null;
    setDbLevel(0);
  }, []);

  const startMeter = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      meterStreamRef.current = stream;
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i]! - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / data.length);
        setDbLevel(Math.min(1, rms * 3));
        meterRafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch (err) {
      // Mic permission denied or device unavailable. Tell the user instead of
      // silently freezing — they otherwise see Talk do nothing on click.
      teardownMeter();
      const denied =
        err instanceof DOMException &&
        (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError');
      setStatus(
        denied
          ? 'Microphone blocked — check browser permissions'
          : 'Microphone unavailable',
        'yellow',
      );
    }
  }, [setStatus, teardownMeter]);

  /** Skip Vapi entirely under test automation (navigator.webdriver === true) —
   * headless Chromium can't grant mic permission, so Vapi hangs in 'listening'. */
  const isAutomated = typeof navigator !== 'undefined' && Boolean((navigator as Navigator).webdriver);

  /** Initialise Vapi lazily once. */
  useEffect(() => {
    if (vapiRef.current || !env.VAPI_PUBLIC_KEY || !env.VAPI_ENABLED || isAutomated) return;
    try {
      const instance = new Vapi(env.VAPI_PUBLIC_KEY);
      instance.on('call-start', () => {
        vapiCallStartAtRef.current = Date.now();
        vapiGotTranscriptRef.current = false;
        vapiAccumulatedRef.current = '';
        userInitiatedStopRef.current = false;
        setState('listening');
        setTransport('vapi');
        setVoice({ voiceState: 'listening', voiceTransport: 'vapi', voiceLiveCaption: '' });
        setStatus('Listening...', 'green');
        void startMeter();
      });
      instance.on('call-end', () => {
        const duration = vapiCallStartAtRef.current
          ? Date.now() - vapiCallStartAtRef.current
          : 0;
        const accumulated = vapiAccumulatedRef.current.trim();
        const userStopped = userInitiatedStopRef.current;
        userInitiatedStopRef.current = false;
        // Only treat short+silent calls as broken when the *server* hung up. If the
        // user clicked Stop before saying anything, that's user intent, not a Vapi
        // failure — don't downgrade the rest of the session to browser STT.
        const shortAndSilent =
          !userStopped && duration > 0 && duration < 3000 && !vapiGotTranscriptRef.current;
        setState('idle');
        setTransport('none');
        setVoice({ voiceState: 'idle', voiceTransport: 'none', voiceLiveCaption: '' });
        teardownMeter();
        if (shortAndSilent) {
          // Assistant ID/key likely invalid for this account. Switch this session to
          // browser SpeechRecognition and retry immediately so the user isn't left
          // staring at a "Talk" button that flashes on and off.
          vapiBrokenRef.current = true;
          if (!startBrowserRef.current?.()) {
            setStatus('Voice unavailable (check Vapi setup)', 'yellow');
          }
          return;
        }
        if (accumulated) {
          onTranscriptRef.current(accumulated);
          vapiAccumulatedRef.current = '';
        } else {
          setStatus('Ready', 'green');
        }
      });
      // Vapi error events are a stronger broken-signal than duration heuristics.
      instance.on('error', () => {
        vapiBrokenRef.current = true;
      });
      instance.on('message', (msg: unknown) => {
        if (!msg || typeof msg !== 'object') return;
        const m = msg as { type?: string; transcriptType?: string; role?: string; transcript?: string };
        // Accumulate final user segments instead of submitting each one. This lets the
        // user pause mid-sentence without Deepgram's endpointing cutting them off —
        // the full utterance is submitted only when the Stop button ends the call.
        if (m.type === 'transcript' && m.transcriptType === 'final' && m.role === 'user' && m.transcript) {
          vapiGotTranscriptRef.current = true;
          const next = (vapiAccumulatedRef.current + ' ' + m.transcript).trim();
          vapiAccumulatedRef.current = next;
          setVoice({ voiceLiveCaption: next });
        }
      });
      vapiRef.current = instance;
    } catch {
      // SDK init failed — stay in browser-fallback mode.
    }
    // onTranscript is intentionally NOT in the dep array — we read it through
    // onTranscriptRef so this effect runs once per mount, not per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAutomated, setStatus, setVoice, startMeter, teardownMeter]);

  useEffect(() => () => teardownMeter(), [teardownMeter]);

  // Forward-reference so the Vapi call-end handler (declared earlier in the
   // useEffect) can invoke the browser fallback once the ref is wired below.
  const startBrowserRef = useRef<(() => boolean) | null>(null);

  const startBrowser = useCallback((): boolean => {
    // Under automation the Web Speech API exists but never fires onerror/onend —
    // claim unsupported so callers show "Voice unavailable" instead of hanging.
    if (!SpeechRecognitionImpl || isAutomated) return false;
    const r = new SpeechRecognitionImpl();
    r.lang = selectedLanguage;
    r.continuous = env.USE_CONTINUOUS_VOICE;
    r.interimResults = env.USE_CONTINUOUS_VOICE;

    if (!env.USE_CONTINUOUS_VOICE) {
      let gotTranscript = false;
      r.onresult = (e) => {
        const first = e.results[0];
        if (!first) return;
        const t = first[0].transcript;
        if (t) {
          gotTranscript = true;
          onTranscriptRef.current(t);
        }
      };
      const finish = () => {
        recognitionRef.current = null;
        setState('idle');
        setTransport('none');
        setVoice({ voiceState: 'idle', voiceTransport: 'none', voiceLiveCaption: '' });
        teardownMeter();
        // Only reset to Ready when no transcript fired — otherwise submitQuery owns the status.
        if (!gotTranscript) setStatus('Ready', 'green');
      };
      r.onend = finish;
      r.onerror = finish;
    } else {
      let finalBuf = '';
      let live = '';
      r.onresult = (e) => {
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i];
          if (!res) continue;
          const piece = res[0]?.transcript ?? '';
          if (res.isFinal) finalBuf += piece;
          else interim += piece;
        }
        live = (finalBuf + interim).trim();
        setLiveCaption(live);
        setVoice({ voiceLiveCaption: live });
      };
      const commit = () => {
        const q = finalBuf.trim() || live.trim();
        if (q) onTranscriptRef.current(q);
        recognitionRef.current = null;
        setState('idle');
        setTransport('none');
        setVoice({ voiceState: 'idle', voiceTransport: 'none', voiceLiveCaption: '' });
        teardownMeter();
        if (!q) setStatus('Ready', 'green');
      };
      r.onend = commit;
      r.onerror = commit;
    }

    recognitionRef.current = r;
    try {
      r.start();
    } catch {
      recognitionRef.current = null;
      return false;
    }
    setState('listening');
    setTransport('browser');
    setVoice({ voiceState: 'listening', voiceTransport: 'browser', voiceLiveCaption: '' });
    setStatus('Listening...', 'green');
    void startMeter();
    return true;
    // onTranscript flows through onTranscriptRef; keep it out of deps so callers
    // passing inline arrows don't churn this callback identity every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [SpeechRecognitionImpl, isAutomated, selectedLanguage, setStatus, setVoice, startMeter, teardownMeter]);

  useEffect(() => {
    startBrowserRef.current = startBrowser;
  }, [startBrowser]);

  const start = useCallback((): void => {
    if (state !== 'idle') return;
    if (
      vapiRef.current &&
      env.VAPI_ASSISTANT_ID &&
      env.VAPI_ENABLED &&
      !isAutomated &&
      !vapiBrokenRef.current
    ) {
      try {
        const maybePromise = vapiRef.current.start(env.VAPI_ASSISTANT_ID);
        // Vapi .start() is async; surface rejections so we can fall back cleanly.
        if (maybePromise && typeof (maybePromise as Promise<unknown>).then === 'function') {
          (maybePromise as Promise<unknown>).catch(() => {
            // Vapi call failed to connect — reset state and try browser fallback.
            setState('idle');
            setTransport('none');
            setVoice({ voiceState: 'idle', voiceTransport: 'none', voiceLiveCaption: '' });
            setStatus('Ready', 'green');
            teardownMeter();
            if (!startBrowser()) {
              setStatus('Voice unavailable', 'yellow');
            }
          });
        }
        return;
      } catch {
        // Synchronous throw — fall through to browser.
      }
    }
    if (!startBrowser()) {
      setStatus('Voice unavailable', 'yellow');
    }
  }, [isAutomated, setStatus, setVoice, state, startBrowser, teardownMeter]);

  const stop = useCallback((): void => {
    if (transport === 'vapi' && vapiRef.current) {
      // Mark this as a user-initiated stop so the call-end handler doesn't trip
      // the broken-flag heuristic when the user pressed Stop before speaking.
      userInitiatedStopRef.current = true;
      try {
        vapiRef.current.stop();
      } catch {
        // ignore
      }
    }
    if (transport === 'browser' && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }
    setState('idle');
    setTransport('none');
    setVoice({ voiceState: 'idle', voiceTransport: 'none', voiceLiveCaption: '' });
    setStatus('Ready', 'green');
    teardownMeter();
  }, [setStatus, setVoice, teardownMeter, transport]);

  const speak = useCallback(
    (text: string, language: string, onEnd?: () => void): void => {
      if (!text || typeof window === 'undefined' || !('speechSynthesis' in window)) {
        onEnd?.();
        return;
      }
      window.speechSynthesis.cancel();
      const detected = detectLanguageFromText(text, language);
      const u = new SpeechSynthesisUtterance(text);
      u.lang = detected;
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find(
        (v) => v.lang === u.lang && (v.name.includes('Neural') || v.name.includes('Google')),
      );
      if (preferred) u.voice = preferred;
      u.onstart = () => {
        setState('speaking');
        setVoice({ voiceState: 'speaking' });
        setStatus('Speaking...', 'blue');
      };
      const done = () => {
        setState('idle');
        setVoice({ voiceState: 'idle' });
        setStatus('Ready', 'green');
        onEnd?.();
      };
      u.onend = done;
      u.onerror = done;
      window.speechSynthesis.speak(u);
    },
    [setStatus, setVoice],
  );

  return { state, transport, liveCaption, start, stop, speak, isSupported, dbLevel };
}
