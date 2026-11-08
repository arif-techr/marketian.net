import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmButton, Empty, PageHeader, Pill, Spinner, useToast } from '../components/ui';
import { api } from '../lib/api';
import { dateTime, plural } from '../lib/format';
import type { ShareGrant, ShareInvite, ShareItems, SharingOverview } from '../lib/types';

const KIND: Record<ShareGrant['kind'], string> = { account: 'WhatsApp account', list: 'Contact list', template: 'Template' };
const STATUS: Record<ShareInvite['status'], [string, string]> = {
  pending: ['Waiting for the code', 'warn'], accepted: ['Accepted', 'ok'], declined: ['Declined', 'bad'],
  cancelled: ['Cancelled', ''], failed: ['Too many wrong codes', 'bad'], expired: ['Code expired', 'bad'],
};

/** mm:ss until `to`, ticking every second. */
function useSecondsLeft(to: string) {
  const [, tick] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => tick(x => x + 1), 1000);
    return () => window.clearInterval(t);
  }, []);
  return Math.max(0, Math.floor((new Date(to).getTime() - Date.now()) / 1000));
}
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

function ItemList({ items }: { items: ShareItems }) {
  const rows = [
    ...items.accounts.map(a => ['WhatsApp account', `${a.label}${a.phone ? ` (+${a.phone})` : ''}`]),
    ...items.lists.map(l => ['Contact list', `${l.name}${l.contact_count !== undefined ? ` · ${plural(l.contact_count, 'contact')}` : ''}`]),
    ...items.templates.map(t => ['Template', t.title]),
  ];
  return (
    <ul className="list">
      {rows.map(([kind, name], i) => <li key={i}><span className="grow">{name}</span><span className="meta">{kind}</span></li>)}
    </ul>
  );
}

export default function Sharing() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['sharing'],
    queryFn: () => api<SharingOverview>('/sharing/'),
    refetchInterval: 5000, // see "Accepted" appear while the code is on screen
  });
  const refresh = () => {
    for (const k of ['sharing', 'accounts', 'contact-lists', 'contacts', 'templates', 'contact-fields', 'dashboard']) qc.invalidateQueries({ queryKey: [k] });
  };

  if (isLoading || !data) return <Spinner />;
  return (
    <>
      <PageHeader title="Share resources" sub="Let another user send from your WhatsApp accounts, send to your contact lists, or use your templates. They can use what you share, but can't change it." />
      {data.received_invites.map(inv => <Incoming key={inv.id} inv={inv} onDone={refresh} />)}
      <div className="grid-2">
        <ShareForm shareable={data.shareable} onDone={refresh} />
        <SentInvites invites={data.sent_invites} onDone={refresh} />
      </div>
      <div className="grid-2">
        <Grants title="Shared by you" empty="You haven't shared anything yet." grants={data.shared_by_me} who="grantee" action="Stop sharing" onDone={refresh} />
        <Grants title="Shared with you" empty="Nothing has been shared with you." grants={data.shared_with_me} who="owner" action="Remove" onDone={refresh} />
      </div>
    </>
  );
}

/** An offer from another user: details, the code box and Accept. */
function Incoming({ inv, onDone }: { inv: ShareInvite; onDone: () => void }) {
  const toast = useToast();
  const [code, setCode] = useState('');
  const left = useSecondsLeft(inv.expires_at);
  const accept = useMutation({
    mutationFn: () => api<ShareInvite & { added: number }>(`/sharing/invites/${inv.id}/accept/`, { method: 'POST', body: { code } }),
    onSuccess: r => { toast(`Accepted. ${plural(r.added, 'item')} from ${inv.from} added, marked "Shared".`); onDone(); },
    onError: (e: Error) => { toast(e.message, 'bad'); setCode(''); onDone(); },
  });
  const decline = useMutation({
    mutationFn: () => api(`/sharing/invites/${inv.id}/decline/`, { method: 'POST' }),
    onSuccess: () => { toast('Declined'); onDone(); },
  });
  return (
    <section className="panel" style={{ borderColor: 'var(--accent)' }}>
      <div className="row spread">
        <h2><b>{inv.from}</b> wants to share with you</h2>
        <Pill tone={left > 60 ? 'warn' : 'bad'}>{left ? `Code valid for ${mmss(left)}` : 'Code expired'}</Pill>
      </div>
      <ItemList items={inv.items} />
      <form className="row" onSubmit={(e: FormEvent) => { e.preventDefault(); accept.mutate(); }}>
        <input type="text" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} placeholder="Enter 6-digit code"
          value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} aria-label={`Code from ${inv.from}`}
          style={{
            width: '15rem', maxWidth: '100%', textAlign: 'center', padding: '10px 14px',
            // Spread the digits out only once typed, so the placeholder fits.
            ...(code ? { fontFamily: 'var(--mono)', fontSize: '1.35rem', fontWeight: 700, letterSpacing: '.45em' } : { fontSize: '1rem' }),
          }} />
        <button type="submit" className="primary" disabled={code.length !== 6 || !left || accept.isPending}>{accept.isPending ? 'Checking…' : 'Accept'}</button>
        <button type="button" className="ghost" disabled={decline.isPending} onClick={() => decline.mutate()}>Decline</button>
      </form>
      <p className="small" style={{ margin: 0 }}>
        Ask {inv.from} for the code shown on their screen. {inv.attempts_left < 5 && `${inv.attempts_left} ${inv.attempts_left === 1 ? 'try' : 'tries'} left. `}
        After accepting, these appear in your app with a <b>Shared</b> tag.
      </p>
    </section>
  );
}

function ShareForm({ shareable, onDone }: { shareable: ShareItems; onDone: () => void }) {
  const toast = useToast();
  const [username, setUsername] = useState('');
  const [picked, setPicked] = useState<{ accounts: number[]; lists: number[]; templates: number[] }>({ accounts: [], lists: [], templates: [] });
  const [made, setMade] = useState<ShareInvite | null>(null);
  const count = picked.accounts.length + picked.lists.length + picked.templates.length;

  const create = useMutation({
    mutationFn: () => api<ShareInvite>('/sharing/invites/', {
      method: 'POST', body: { username: username.trim(), account_ids: picked.accounts, list_ids: picked.lists, template_ids: picked.templates },
    }),
    onSuccess: inv => { setMade(inv); onDone(); },
    onError: (e: Error) => toast(e.message, 'bad'),
  });

  if (made) return <CodeScreen inv={made} onClose={() => { setMade(null); setUsername(''); setPicked({ accounts: [], lists: [], templates: [] }); onDone(); }} onNewCode={setMade} />;

  const group = (key: keyof typeof picked, title: string, items: { id: number; text: string }[]) => (
    <fieldset className="opts">
      <legend>{title}</legend>
      {items.length ? items.map(it => (
        <label key={it.id} className="row">
          <input type="checkbox" checked={picked[key].includes(it.id)}
            onChange={e => setPicked({ ...picked, [key]: e.target.checked ? [...picked[key], it.id] : picked[key].filter(x => x !== it.id) })} />
          {it.text}
        </label>
      )) : <span className="small">None yet.</span>}
    </fieldset>
  );

  return (
    <form className="panel" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }}>
      <h2>Share with someone</h2>
      <label className="field"><span>Their username</span>
        <input type="text" value={username} onChange={e => setUsername(e.target.value)} required maxLength={150} autoComplete="off" placeholder="e.g. niloy" />
      </label>
      {group('accounts', 'WhatsApp accounts', shareable.accounts.map(a => ({ id: a.id, text: `${a.label}${a.phone ? ` (+${a.phone})` : ''}` })))}
      {group('lists', 'Contact lists', shareable.lists.map(l => ({ id: l.id, text: l.name })))}
      {group('templates', 'Templates', shareable.templates.map(t => ({ id: t.id, text: t.title })))}
      <p className="small" style={{ margin: 0 }}>
        A shared WhatsApp account can be sent from, but its QR code is never shown and they can't change or remove it. A shared list
        lets them see and message its contacts (not your other contacts). You can stop sharing any time.
      </p>
      <div className="row">
        <button type="submit" className="primary" disabled={!username.trim() || !count || create.isPending}>
          {create.isPending ? 'Creating…' : `Share ${count ? plural(count, 'item') : ''} and show code`}
        </button>
      </div>
    </form>
  );
}

/** The one-time code, shown big with its countdown. The other user types it to accept. */
function CodeScreen({ inv, onClose, onNewCode }: { inv: ShareInvite; onClose: () => void; onNewCode: (inv: ShareInvite) => void }) {
  const toast = useToast();
  const left = useSecondsLeft(inv.expires_at);
  const status = useQuery({
    queryKey: ['sharing'], queryFn: () => api<SharingOverview>('/sharing/'), refetchInterval: 3000,
    select: d => d.sent_invites.find(i => i.id === inv.id)?.status,
  });
  const again = useMutation({
    mutationFn: () => api<ShareInvite>(`/sharing/invites/${inv.id}/new-code/`, { method: 'POST' }),
    onSuccess: onNewCode,
    onError: (e: Error) => toast(e.message, 'bad'),
  });
  const cancel = useMutation({ mutationFn: () => api(`/sharing/invites/${inv.id}/cancel/`, { method: 'POST' }), onSuccess: onClose });
  const accepted = status.data === 'accepted';
  const dead = !accepted && (!left || status.data === 'failed' || status.data === 'declined');

  return (
    <section className="panel" style={{ textAlign: 'center' }}>
      <h2>{accepted ? `${inv.to} accepted` : `Give this code to ${inv.to}`}</h2>
      {accepted ? (
        <p className="note ok">Shared. {inv.to} now sees these items with a <b>Shared</b> tag.</p>
      ) : (<>
        <div aria-live="polite" style={{ fontFamily: 'var(--mono)', fontSize: '2.6rem', fontWeight: 700, letterSpacing: '.35em', opacity: dead ? 0.35 : 1 }}>
          {inv.code}
        </div>
        <p className={dead ? 'err' : 'small'} style={{ margin: 0 }}>
          {status.data === 'declined' ? `${inv.to} declined.` : status.data === 'failed' ? 'Too many wrong codes.'
            : left ? <>Valid for <b>{mmss(left)}</b>. {inv.to} enters it under <b>Share resources</b> and presses Accept.</> : 'The code has expired.'}
        </p>
      </>)}
      <ItemList items={inv.items} />
      <div className="row" style={{ justifyContent: 'center' }}>
        {dead && status.data !== 'declined' && <button type="button" className="primary" disabled={again.isPending} onClick={() => again.mutate()}>New code</button>}
        {!accepted && !dead && <button type="button" className="ghost" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel</button>}
        <button type="button" onClick={onClose}>{accepted ? 'Done' : 'Close'}</button>
      </div>
    </section>
  );
}

function SentInvites({ invites, onDone }: { invites: ShareInvite[]; onDone: () => void }) {
  const toast = useToast();
  const [shown, setShown] = useState<ShareInvite | null>(null);
  const again = useMutation({
    mutationFn: (id: number) => api<ShareInvite>(`/sharing/invites/${id}/new-code/`, { method: 'POST' }),
    onSuccess: inv => { setShown(inv); onDone(); },
    onError: (e: Error) => toast(e.message, 'bad'),
  });
  if (shown) return <CodeScreen inv={shown} onNewCode={setShown} onClose={() => { setShown(null); onDone(); }} />;
  return (
    <section className="panel">
      <h2>Your invitations</h2>
      {invites.length ? (
        <ul className="list">
          {invites.map(inv => {
            const [label, tone] = STATUS[inv.status];
            const n = inv.items.accounts.length + inv.items.lists.length + inv.items.templates.length;
            return (
              <li key={inv.id}>
                <span className="grow">
                  <span className="name">To {inv.to}</span>
                  <span className="small">{plural(n, 'item')} · {dateTime(inv.created_at)}</span>
                </span>
                <Pill tone={tone}>{label}</Pill>
                {(inv.status === 'pending' || inv.status === 'expired' || inv.status === 'failed') && (
                  <button type="button" className="ghost" disabled={again.isPending} onClick={() => again.mutate(inv.id)}
                    title="Codes are shown only once; this makes a fresh one">{inv.status === 'pending' ? 'Show new code' : 'New code'}</button>
                )}
              </li>
            );
          })}
        </ul>
      ) : <Empty>No invitations in the last day.</Empty>}
    </section>
  );
}

function Grants({ title, empty, grants, who, action, onDone }: {
  title: string; empty: string; grants: ShareGrant[]; who: 'owner' | 'grantee'; action: string; onDone: () => void;
}) {
  const toast = useToast();
  return (
    <section className="panel">
      <h2>{title}</h2>
      {grants.length ? (
        <ul className="list">
          {grants.map(g => (
            <li key={g.id}>
              <span className="grow">
                <span className="name">{g.name}{g.detail ? ` (${g.detail})` : ''}</span>
                <span className="small">{KIND[g.kind]} · {who === 'grantee' ? `with ${g.grantee}` : `from ${g.owner}`} · since {dateTime(g.created_at)}</span>
              </span>
              <ConfirmButton confirm={`${action}?`} onConfirm={async () => {
                try { await api(`/sharing/shares/${g.id}/`, { method: 'DELETE' }); toast(who === 'grantee' ? 'Stopped sharing' : 'Removed'); onDone(); }
                catch (e) { toast((e as Error).message, 'bad'); }
              }}>{action}</ConfirmButton>
            </li>
          ))}
        </ul>
      ) : <Empty>{empty}</Empty>}
    </section>
  );
}
