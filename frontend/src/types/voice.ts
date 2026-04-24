export type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';

export type VoiceTransport = 'vapi' | 'browser' | 'none';

export interface VoiceStatus {
  state: VoiceState;
  transport: VoiceTransport;
  liveCaption: string;
  error: string | null;
}
