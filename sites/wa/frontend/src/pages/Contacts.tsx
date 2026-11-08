import { useState, type FormEvent } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmButton, Empty, PageHeader, Pill, SharedTag, Spinner, useToast } from '../components/ui';
import { api, upload } from '../lib/api';
import { plural } from '../lib/format';
import type { ColumnUse, Contact, ContactList, ImportPreview, ImportResult, Page, Validation } from '../lib/types';

export const formatPhone = (p: string) => '+' + p;

export default function Contacts() {
  const toast = useToast();
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [listFilter, setListFilter] = useState<number | ''>('');
  const [valid, setValid] = useState<'' | 'yes' | 'no' | 'pending'>('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [panel, setPanel] = useState<'add' | 'import' | null>(null);

  const params = new URLSearchParams({ page: String(page) });
  if (q.trim()) params.set('q', q.trim());
  if (listFilter) params.set('list', String(listFilter));
  if (valid) params.set('valid', valid);
  const exportParams = new URLSearchParams(params);
  exportParams.delete('page');

  const contacts = useQuery({
    queryKey: ['contacts', q, listFilter, valid, page],
    queryFn: () => api<Page<Contact>>(`/contacts/?${params}`),
    placeholderData: keepPreviousData,
  });
  // Numbers are checked for WhatsApp in the background; poll while some are still waiting.
  const checks = useQuery({
    queryKey: ['contacts', 'validation'],
    queryFn: () => api<Validation>('/contacts/validation/'),
    refetchInterval: r => (r.state.data?.pending ? 5000 : false),
  });
  const lists = useQuery({ queryKey: ['contact-lists'], queryFn: () => api<ContactList[]>('/contact-lists/') });
  const listName = (id: number) => lists.data?.find(l => l.id === id)?.name ?? '';
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['contacts'] });
    qc.invalidateQueries({ queryKey: ['contact-lists'] });
  };

  const bulk = useMutation({
    mutationFn: (body: { action: string; list_id?: number }) =>
      api<{ affected: number }>('/contacts/bulk/', { method: 'POST', body: { ...body, ids: [...selected] } }),
    onSuccess: (r, v) => {
      toast(`${plural(r.affected, 'contact')} ${{ delete: 'deleted', opt_out: 'opted out', opt_in: 'opted back in', add_to_list: 'added to the list', remove_from_list: 'removed from the list', recheck: 'queued to be checked again' }[v.action as 'delete']}`);
      if (v.action === 'delete') setSelected(new Set());
      refresh();
    },
    onError: (e: Error) => toast(e.message, 'bad'),
  });

  async function selectAllMatching() {
    const p = new URLSearchParams(params);
    p.delete('page');
    const ids = await api<number[]>(`/contacts/ids/?${p}`);
    setSelected(new Set(ids));
  }

  const rows = contacts.data?.results ?? [];
  const pages = contacts.data ? Math.max(1, Math.ceil(contacts.data.count / 50)) : 1;
  const allOnPage = rows.length > 0 && rows.every(c => selected.has(c.id));

  return (
    <>
      <PageHeader
        title="Contacts"
        sub="People you can message directly, one by one. Organise them into lists to send to a whole list at once."
        actions={
          <>
            <a className="btn" href={`/api/contacts/export/?${exportParams}`} download>Export CSV</a>
            <button type="button" onClick={() => setPanel(panel === 'add' ? null : 'add')}>Add contact</button>
            <button type="button" className="primary" onClick={() => setPanel(panel === 'import' ? null : 'import')}>Import</button>
          </>
        }
      />

      <div className="note">
        Only message people who expect to hear from you. Messages to numbers that haven't saved yours are the main reason
        WhatsApp bans accounts. Mark anyone who asks to stop as <b>opted out</b>, and they will always be skipped.
      </div>

      {panel === 'add' && <AddContact lists={lists.data ?? []} onDone={() => { setPanel(null); refresh(); }} />}
      {panel === 'import' && <ImportContacts lists={lists.data ?? []} onDone={() => { refresh(); }} />}

      <div className="grid-side">
        <section className="panel">
          <h2>Lists</h2>
          <ul className="list">
            <li className={listFilter === '' ? 'active' : ''}>
              <button type="button" className="row-btn" onClick={() => { setListFilter(''); setPage(1); }}>All contacts</button>
            </li>
            {lists.data?.map(l => (
              <li key={l.id} className={listFilter === l.id ? 'active' : ''}>
                <button type="button" className="row-btn" onClick={() => { setListFilter(l.id); setPage(1); }}>
                  <span className="grow">{l.name} <SharedTag by={l.shared_by} /></span><span className="meta">{l.contact_count}</span>
                </button>
                {!l.shared_by && <ConfirmButton className="ghost x" confirm="Delete list?" onConfirm={async () => {
                  await api(`/contact-lists/${l.id}/`, { method: 'DELETE' });
                  if (listFilter === l.id) setListFilter('');
                  refresh();
                }}>✕</ConfirmButton>}
              </li>
            ))}
          </ul>
          <NewList onCreated={refresh} />
        </section>

        <section className="panel">
          <div className="row spread">
            <input type="search" placeholder="Search name or number" value={q} onChange={e => { setQ(e.target.value); setPage(1); }} style={{ maxWidth: 320 }} />
            <select aria-label="Filter by WhatsApp check" value={valid} onChange={e => { setValid(e.target.value as typeof valid); setPage(1); }}>
              <option value="">Any WhatsApp status</option>
              <option value="yes">On WhatsApp</option>
              <option value="no">Not on WhatsApp</option>
              <option value="pending">Not checked yet</option>
            </select>
            <span className="meta">{contacts.data ? plural(contacts.data.count, 'contact') : ''}</span>
          </div>
          {checks.data && checks.data.total > 0 && (
            <p className="small" style={{ margin: 0 }}>
              {checks.data.valid.toLocaleString()} on WhatsApp · {checks.data.invalid.toLocaleString()} not on WhatsApp
              {checks.data.pending ? ` · ${checks.data.pending.toLocaleString()} being checked (needs a connected account)` : ''}.
              {' '}Numbers not on WhatsApp are left out of broadcasts automatically.
            </p>
          )}

          {selected.size > 0 && (
            <div className="row toolbar">
              <b>{selected.size} selected</b>
              <select aria-label="Add selected to list" value="" onChange={e => e.target.value && bulk.mutate({ action: 'add_to_list', list_id: Number(e.target.value) })}>
                <option value="">Add to list…</option>
                {lists.data?.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
              {listFilter !== '' && <button type="button" onClick={() => bulk.mutate({ action: 'remove_from_list', list_id: listFilter })}>Remove from this list</button>}
              <button type="button" onClick={() => bulk.mutate({ action: 'opt_out' })}>Opt out</button>
              <button type="button" onClick={() => bulk.mutate({ action: 'opt_in' })}>Opt in</button>
              <button type="button" onClick={() => bulk.mutate({ action: 'recheck' })} title="Check these numbers for WhatsApp again">Re-check</button>
              <ConfirmButton className="danger" confirm={`Delete ${selected.size}?`} onConfirm={() => bulk.mutateAsync({ action: 'delete' })}>Delete</ConfirmButton>
              <button type="button" className="ghost" onClick={() => setSelected(new Set())}>Clear selection</button>
            </div>
          )}

          {contacts.isLoading ? <Spinner /> : rows.length ? (
            <>
              <div className="row small">
                <label className="row"><input type="checkbox" checked={allOnPage} onChange={e => setSelected(s => {
                  const n = new Set(s);
                  rows.forEach(c => (e.target.checked ? n.add(c.id) : n.delete(c.id)));
                  return n;
                })} /> Select page</label>
                {contacts.data && contacts.data.count > rows.length && (
                  <button type="button" className="ghost" onClick={selectAllMatching}>Select all {contacts.data.count}</button>
                )}
              </div>
              <ul className="list">
                {rows.map(c => <ContactRow key={c.id} c={c} checked={selected.has(c.id)} listName={listName}
                  onCheck={on => setSelected(s => { const n = new Set(s); on ? n.add(c.id) : n.delete(c.id); return n; })}
                  onChange={refresh} />)}
              </ul>
            </>
          ) : (
            <Empty>{q || listFilter ? 'No contacts match.' : 'No contacts yet. Add one, or import a list from a spreadsheet.'}</Empty>
          )}

          {pages > 1 && (
            <div className="row spread">
              <button type="button" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Previous</button>
              <span className="meta">Page {page} of {pages}</span>
              <button type="button" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function ContactRow({ c, checked, onCheck, onChange, listName }: {
  c: Contact; checked: boolean; onCheck: (on: boolean) => void; onChange: () => void; listName: (id: number) => string;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(c.name);
  const save = useMutation({
    mutationFn: (body: Partial<Contact>) => api<Contact>(`/contacts/${c.id}/`, { method: 'PATCH', body }),
    onSuccess: () => { setEditing(false); onChange(); },
    onError: (e: Error) => toast(e.message, 'bad'),
  });
  const id = `ct-${c.id}`;
  return (
    <li>
      <input type="checkbox" id={id} checked={checked} disabled={!!c.shared_by} onChange={e => onCheck(e.target.checked)} aria-label={`Select ${c.name || c.phone}`} />
      {editing ? (
        <form className="row grow-row" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate({ name }); }}>
          <input type="text" value={name} maxLength={120} onChange={e => setName(e.target.value)} autoFocus style={{ flex: 1, minWidth: 140 }} />
          <button type="submit" className="primary" disabled={save.isPending}>Save</button>
          <button type="button" className="ghost" onClick={() => { setEditing(false); setName(c.name); }}>Cancel</button>
        </form>
      ) : (
        <>
          <label className="grow" htmlFor={id}>
            <span className="name">{c.name || <span className="small">No name</span>}</span>
            <span className="meta">{formatPhone(c.phone)}{c.lists.length ? ' · ' + c.lists.map(listName).filter(Boolean).join(', ') : ''}</span>
            {Object.keys(c.fields ?? {}).length > 0 && (
              <span className="small">{Object.entries(c.fields).map(([k, v]) => `${k}: ${v}`).join(' · ')}</span>
            )}
          </label>
          {c.on_whatsapp === false && <Pill tone="bad" title="The last check found no WhatsApp on this number">Not on WhatsApp</Pill>}
          {c.opted_out && <Pill tone="warn">Opted out</Pill>}
          <SharedTag by={c.shared_by} />
          {!c.shared_by && (
            <span className="row">
              <button type="button" className="ghost" onClick={() => setEditing(true)}>Edit</button>
              <button type="button" className="ghost" onClick={() => save.mutate({ opted_out: !c.opted_out })}>{c.opted_out ? 'Opt in' : 'Opt out'}</button>
            </span>
          )}
        </>
      )}
    </li>
  );
}

function AddContact({ lists, onDone }: { lists: ContactList[]; onDone: () => void }) {
  const toast = useToast();
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [listId, setListId] = useState<number | ''>('');
  const add = useMutation({
    mutationFn: () => api<Contact>('/contacts/', { method: 'POST', body: { phone, name, lists: listId ? [listId] : [] } }),
    onSuccess: c => { toast(`Added ${c.name || '+' + c.phone}`); setPhone(''); setName(''); onDone(); },
    onError: (e: Error) => toast(e.message, 'bad'),
  });
  return (
    <form className="panel" onSubmit={e => { e.preventDefault(); add.mutate(); }}>
      <h2>Add a contact</h2>
      <div className="row">
        <label className="field"><span>Phone number</span>
          <input type="text" inputMode="tel" placeholder="+8801712345678 or 01712345678" value={phone} onChange={e => setPhone(e.target.value)} required />
        </label>
        <label className="field"><span>Name (optional)</span>
          <input type="text" value={name} maxLength={120} onChange={e => setName(e.target.value)} />
        </label>
        <label className="field"><span>List (optional)</span>
          <select value={listId} onChange={e => setListId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">No list</option>
            {lists.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </label>
      </div>
      <div><button className="primary" type="submit" disabled={add.isPending}>Add contact</button></div>
    </form>
  );
}

const USE_LABELS: [ColumnUse, string][] = [['phone', 'Phone number'], ['name', 'Name'], ['field', 'Use in messages'], ['ignore', 'Ignore']];
const fieldKey = (label: string) => label.trim().toLowerCase().replace(/[^\p{L}\p{N}\p{M}_]+/gu, '_').replace(/_+/g, '_').replace(/^_|_$/g, '').slice(0, 40) || 'field';

function ImportContacts({ lists, onDone }: { lists: ContactList[]; onDone: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [uses, setUses] = useState<ColumnUse[]>([]);
  const [hasHeader, setHasHeader] = useState(true);
  const [target, setTarget] = useState<string>('');
  const [newList, setNewList] = useState('');
  const [result, setResult] = useState<ImportResult | null>(null);

  const listBody = { list_id: target && target !== 'new' ? String(target) : '', new_list: target === 'new' ? newList : '' };

  const look = useMutation({
    mutationFn: () => file
      ? upload<ImportPreview>('/contacts/import/preview/', file)
      : api<ImportPreview>('/contacts/import/preview/', { method: 'POST', body: { text } }),
    onSuccess: p => { setPreview(p); setUses(p.columns); setHasHeader(p.has_header); setResult(null); },
    onError: (e: Error) => toast(e.message, 'bad'),
  });

  const run = useMutation({
    mutationFn: () => {
      const common = { ...listBody, has_header: String(hasHeader) };
      if (preview && file) return upload<ImportResult>('/contacts/import/', file, undefined, { ...common, columns: JSON.stringify(uses) });
      return api<ImportResult>('/contacts/import/', {
        method: 'POST',
        body: preview
          ? { text, columns: uses, has_header: hasHeader, list_id: listBody.list_id ? Number(listBody.list_id) : null, new_list: listBody.new_list }
          : { text, list_id: listBody.list_id ? Number(listBody.list_id) : null, new_list: listBody.new_list },
      });
    },
    onSuccess: r => {
      setResult(r); setText(''); setFile(null); setPreview(null);
      qc.invalidateQueries({ queryKey: ['contact-fields'] });
      toast(`Imported ${plural(r.total, 'number')}`);
      onDone();
    },
    onError: (e: Error) => toast(e.message, 'bad'),
  });

  function chooseFile(f: File | undefined) {
    if (!f) return;
    if (f.size > 5_000_000) return toast('That file is too large (5 MB max). Split it into smaller files.', 'bad');
    setFile(f); setText(''); setPreview(null); setResult(null);
  }

  const headers = preview ? (hasHeader ? preview.headers : preview.headers.map((_, i) => `Column ${i + 1}`)) : [];
  const rows = preview ? (hasHeader || !preview.has_header ? preview.sample : [preview.headers, ...preview.sample].slice(0, 5)) : [];
  const setUse = (i: number, u: ColumnUse) => setUses(cur => cur.map((x, j) => (j === i ? u : (u === 'phone' && x === 'phone' ? 'ignore' : x))));
  const ready = !!(file || text.trim());

  return (
    <form className="panel" onSubmit={e => { e.preventDefault(); if (preview || !file) run.mutate(); else look.mutate(); }}>
      <h2>Import contacts</h2>
      <p className="small" style={{ margin: 0 }}>
        Upload an <b>Excel (.xlsx)</b> or <b>CSV</b> file, or paste one contact per line. Then choose what each column is:
        the phone number, the name, or <b>Use in messages</b> for anything else you want to put in messages, like Score or Due amount
        (it becomes <code className="inline">{'{score}'}</code> in templates). Numbers already saved are updated, not duplicated.
      </p>

      {!preview && (<>
        {file ? (
          <div className="filechip"><span>📄 {file.name}</span>
            <button type="button" className="ghost" aria-label="Remove file" onClick={() => setFile(null)}>✕</button>
          </div>
        ) : (
          <textarea value={text} onChange={e => setText(e.target.value)} placeholder={'Name, Phone, Score\nRahim, 01712345678, 85\nKarim, 01812345678, 72'} style={{ minHeight: 120 }} />
        )}
        <div className="row">
          <label className="filebtn">{file ? 'Choose another file' : 'Upload Excel or CSV'}
            <input type="file" hidden accept=".xlsx,.csv,.txt,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/plain"
              onChange={e => { chooseFile(e.target.files?.[0]); e.target.value = ''; }} />
          </label>
          <button type="button" className="primary" disabled={!ready || look.isPending} onClick={() => look.mutate()}>
            {look.isPending ? 'Reading…' : 'Next: choose columns'}
          </button>
          {!file && <button type="submit" className="ghost" disabled={!text.trim() || run.isPending} title="Import names and numbers only, without choosing columns">Quick import</button>}
        </div>
      </>)}

      {preview && (<>
        <div className="row spread">
          <span className="small">{file ? file.name : 'Pasted text'} · {plural(preview.total_rows + (preview.has_header && !hasHeader ? 1 : 0), 'row')}</span>
          <label className="row small"><input type="checkbox" checked={hasHeader} onChange={e => setHasHeader(e.target.checked)} /> First row is headings</label>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>{headers.map((h, i) => <th key={i}>{h}</th>)}</tr>
              <tr>
                {headers.map((h, i) => (
                  <th key={i}>
                    <select aria-label={`Use of column ${h}`} value={uses[i] ?? 'ignore'} onChange={e => setUse(i, e.target.value as ColumnUse)}>
                      {USE_LABELS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
                    </select>
                    {uses[i] === 'field' && <div className="small" style={{ fontWeight: 400 }}>{`{${fieldKey(hasHeader ? h : `column_${i + 1}`)}}`}</div>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => <tr key={ri}>{headers.map((_, i) => <td key={i} className="small">{r[i] ?? ''}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
        {!uses.includes('phone') && <p className="err" style={{ margin: 0 }}>Choose which column has the phone numbers.</p>}
        <div className="row">
          <select value={target} onChange={e => setTarget(e.target.value)} aria-label="Add imported contacts to a list">
            <option value="">Don't add to a list</option>
            {lists.map(l => <option key={l.id} value={l.id}>Add to "{l.name}"</option>)}
            <option value="new">Add to a new list…</option>
          </select>
          {target === 'new' && <input type="text" placeholder="New list name" value={newList} maxLength={80} onChange={e => setNewList(e.target.value)} style={{ maxWidth: 220 }} required />}
          <button className="primary" type="submit" disabled={!uses.includes('phone') || run.isPending}>{run.isPending ? 'Importing…' : 'Import'}</button>
          <button type="button" className="ghost" onClick={() => setPreview(null)}>Back</button>
        </div>
      </>)}

      {result && (
        <div className={result.invalid_count ? 'note' : 'note ok'}>
          {plural(result.created, 'new contact')}, {plural(result.updated, 'name')} updated{result.list ? `, added to "${result.list.name}"` : ''}.
          {result.fields?.length > 0 && <> Columns for messages: {result.fields.map(k => <code key={k} className="inline">{`{${k}}`}</code>)}{result.fields_updated ? ` (${plural(result.fields_updated, 'contact')} got new values)` : ''}. Use them with <b>+ Field</b> in a template.</>}
          {result.columns && ` Names from the "${result.columns.name_column ?? '(none)'}" column, numbers from "${result.columns.phone_column ?? 'any column'}"; other columns were ignored.`}
          {result.garbled_names > 0 && <><br />{plural(result.garbled_names, 'name')} came through as "???": the file lost its Bangla letters. Upload the .xlsx file instead, or in Excel use <b>Save As → CSV UTF-8</b>.</>}
          {result.validation?.pending > 0 && ` ${plural(result.validation.pending, 'number')} will now be checked for WhatsApp in the background.`}
          {result.invalid_count > 0 && (
            <>
              {' '}{plural(result.invalid_count, 'row')} had no valid number and were skipped:
              <ul className="small">{result.invalid.slice(0, 10).map(i => <li key={i.line}>Row {i.line}: {i.text}</li>)}</ul>
            </>
          )}
        </div>
      )}
    </form>
  );
}

function NewList({ onCreated }: { onCreated: () => void }) {
  const toast = useToast();
  const [name, setName] = useState('');
  return (
    <form className="row" onSubmit={async e => {
      e.preventDefault();
      try { await api('/contact-lists/', { method: 'POST', body: { name } }); setName(''); onCreated(); }
      catch (err) { toast((err as Error).message, 'bad'); }
    }}>
      <input type="text" placeholder="New list" value={name} maxLength={80} onChange={e => setName(e.target.value)} style={{ flex: 1, minWidth: 120 }} />
      <button type="submit" disabled={!name.trim()}>Create</button>
    </form>
  );
}
