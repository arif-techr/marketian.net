import type { AccountStatus, CampaignStatus, TargetStatus } from './types';

const ENTITIES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (s: string) => s.replace(/[&<>"']/g, c => ENTITIES[c]);

/** WhatsApp markup (*bold* _italic_ ~strike~ ```mono```) to safe HTML for the preview. */
export function waToHtml(text: string): string {
  let h = esc(text);
  h = h.replace(/```([\s\S]+?)```/g, '<code>$1</code>');
  for (const [m, tag] of [['\\*', 'b'], ['_', 'i'], ['~', 's']] as const) {
    h = h.replace(new RegExp(`(^|[\\s(])${m}(\\S(?:[^${m}\\n]*\\S)?)${m}(?=$|[\\s.,!?)])`, 'gm'), `$1<${tag}>$2</${tag}>`);
  }
  return h;
}

export function fileSize(n: number): string {
  return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB';
}

export function duration(sec: number): string {
  if (sec < 90) return Math.round(sec) + ' seconds';
  const m = Math.round(sec / 60);
  return m < 90 ? m + ' minutes' : (m / 60).toFixed(1) + ' hours';
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
}

export function relative(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return Math.round(s / 60) + ' min ago';
  if (s < 86400) return Math.round(s / 3600) + ' h ago';
  return dateTime(iso);
}

export const plural = (n: number, word: string) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`;

/** Value for <input type="datetime-local"> in the browser's time zone. */
export function localInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

type Tone = 'ok' | 'warn' | 'bad' | 'info' | '';

export const accountStatus: Record<AccountStatus, [string, Tone]> = {
  starting: ['Starting…', 'warn'],
  qr: ['Scan the QR code', 'warn'],
  connected: ['Connected', 'ok'],
  reconnecting: ['Reconnecting…', 'warn'],
  disconnected: ['Not linked', ''],
  logged_out: ['Logged out from phone', 'bad'],
  error: ['Error', 'bad'],
};

export const campaignStatus: Record<CampaignStatus, [string, Tone]> = {
  scheduled: ['Scheduled', 'info'],
  running: ['Sending', 'warn'],
  paused: ['Paused', ''],
  completed: ['Completed', 'ok'],
  cancelled: ['Cancelled', 'bad'],
};

export const targetStatus: Record<TargetStatus, [string, Tone]> = {
  pending: ['Waiting', ''],
  sending: ['Sending', 'warn'],
  sent: ['Sent', 'ok'],
  failed: ['Failed', 'bad'],
  skipped: ['Skipped', ''],
};

/** Preview of a personalised message: {name} / {name|fallback} shown with a sample name. */
// Same rule as the server (runner.personalize): {key} or {key|fallback}; only known keys are replaced.
const TAG = /\{([^\s{}|]{1,40})(?:\|([^}]*))?\}/g;

export type Sample = { name?: string; phone?: string; fields?: Record<string, string> };

/** Fill placeholders for one recipient. `known` = the workspace's field keys; other braces stay as typed. */
export function fillFields(text: string, s: Sample, known: Iterable<string> = []): string {
  const keys = new Set(known);
  return text.replace(TAG, (whole, rawKey: string, fallback?: string) => {
    const key = rawKey.toLowerCase();
    const fields = s.fields ?? {};
    let value: string;
    if (key === 'name') value = s.name ?? '';
    else if (key === 'phone') value = s.phone ? `+${s.phone}` : '';
    else if (key in fields || keys.has(key)) value = fields[key] ?? '';
    else return whole;
    return value || (fallback ?? '').trim();
  });
}

/** Preview with a sample name. */
export const previewName = (text: string, name = 'Rahim') => fillFields(text, { name });

export const usesName = (text: string) => /\{name/i.test(text);

/** Field keys (other than name/phone) that a message uses. */
export const usedFields = (text: string, known: Iterable<string>) => {
  const keys = new Set(known);
  return [...new Set([...text.matchAll(TAG)].map(m => m[1].toLowerCase()))].filter(k => keys.has(k));
};
