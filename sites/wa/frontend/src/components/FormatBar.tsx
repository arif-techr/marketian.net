import { useState, type ReactNode, type RefObject } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { ContactField } from '../lib/types';
import { useToast } from './ui';

export const NAME_TAG = '{name|friend}';

/** The workspace's imported columns, usable in messages as {key}. */
export function useFields() {
  return useQuery({ queryKey: ['contact-fields'], queryFn: () => api<ContactField[]>('/contact-fields/') });
}

/** WhatsApp formatting buttons, "+ Name" and "+ Field" for a message textarea. */
export default function FormatBar({ textRef, value, onChange, children }: {
  textRef: RefObject<HTMLTextAreaElement | null>; value: string; onChange: (v: string) => void; children?: ReactNode;
}) {
  const toast = useToast();
  const qc = useQueryClient();
  const fields = useFields();
  const [naming, setNaming] = useState(false);
  const [label, setLabel] = useState('');

  function wrap(w: string) {
    const el = textRef.current;
    if (!el) return;
    const a = el.selectionStart, z = el.selectionEnd, sel = value.slice(a, z) || 'text';
    onChange(value.slice(0, a) + w + sel + w + value.slice(z));
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(a + w.length, a + w.length + sel.length); });
  }

  function insert(snippet: string) {
    const el = textRef.current;
    const a = el?.selectionStart ?? value.length, z = el?.selectionEnd ?? value.length;
    onChange(value.slice(0, a) + snippet + value.slice(z));
    requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(a + snippet.length, a + snippet.length); });
  }

  const addField = useMutation({
    mutationFn: (l: string) => api<ContactField>('/contact-fields/', { method: 'POST', body: { label: l } }),
    onSuccess: f => {
      qc.invalidateQueries({ queryKey: ['contact-fields'] });
      insert(`{${f.key}}`);
      setNaming(false);
      setLabel('');
      toast(`Added {${f.key}}. Import a "${f.label}" column to fill it for each contact.`);
    },
    onError: (e: Error) => toast(e.message, 'bad'),
  });

  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row fmt" role="group" aria-label="WhatsApp formatting">
        <button type="button" onClick={() => wrap('*')} title="Bold"><b>B</b></button>
        <button type="button" onClick={() => wrap('_')} title="Italic"><i>I</i></button>
        <button type="button" onClick={() => wrap('~')} title="Strikethrough"><s>S</s></button>
        <button type="button" onClick={() => wrap('```')} title="Monospace">{'{ }'}</button>
        <button type="button" onClick={() => insert(NAME_TAG)} title="Each recipient sees their own name here (friend when a contact has no name)">+ Name</button>
        <select aria-label="Insert a field from your imported data" value="" title="Each recipient sees their own value from your imported data"
          onChange={e => {
            const v = e.target.value;
            if (v === '__new') setNaming(true);
            else if (v === '__phone') insert('{phone}');
            else if (v) insert(`{${v}}`);
          }}>
          <option value="">+ Field…</option>
          {fields.data?.map(f => <option key={f.id} value={f.key}>{f.label} → {`{${f.key}}`}{f.shared_by ? ` (shared by ${f.shared_by})` : ''}</option>)}
          <option value="__phone">Phone number → {'{phone}'}</option>
          <option value="__new">New field…</option>
        </select>
        {children}
      </div>
      {naming && (
        <div className="row">
          <input type="text" placeholder="Field name, e.g. Score or Due amount" value={label} maxLength={80} autoFocus
            onChange={e => setLabel(e.target.value)} style={{ flex: 1, minWidth: 180 }} aria-label="New field name"
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); if (label.trim()) addField.mutate(label.trim()); } }} />
          <button type="button" className="primary" disabled={!label.trim() || addField.isPending} onClick={() => addField.mutate(label.trim())}>Add field</button>
          <button type="button" className="ghost" onClick={() => setNaming(false)}>Cancel</button>
        </div>
      )}
    </div>
  );
}
