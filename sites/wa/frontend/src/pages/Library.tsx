import { useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import FormatBar, { NAME_TAG, useFields } from '../components/FormatBar';
import { ConfirmButton, Empty, PageHeader, Pill, SharedTag, useToast } from '../components/ui';
import { api } from '../lib/api';
import { dateTime, fillFields, usedFields, usesName, waToHtml, type Sample } from '../lib/format';
import type { ContactField, Template } from '../lib/types';

export default function Library() {
  return (
    <>
      <PageHeader title="Templates" sub="Messages you send often. Make them personal with + Name and + Field (values from your imported Excel/CSV), then press Send." />
      <Templates />
    </>
  );
}

/** Sample values for a preview: the field's own name in angle brackets, e.g. ‹Score›. */
const sampleFor = (fields: ContactField[] | undefined, name = 'Rahim', overrides: Record<string, string> = {}): Sample => ({
  name, phone: '8801712345678',
  fields: Object.fromEntries((fields ?? []).map(f => [f.key, overrides[f.key] ?? `‹${f.label}›`])),
});

/** A message as the recipient sees it, with sample values filled in. */
function Bubble({ text, sample, known }: { text: string; sample: Sample; known: string[] }) {
  return (
    <div className="chat">
      <div className="bubble">
        {text.trim()
          ? <div dangerouslySetInnerHTML={{ __html: waToHtml(fillFields(text, sample, known)) }} />
          : <span className="empty">Your formatted message appears here.</span>}
      </div>
    </div>
  );
}

function Templates() {
  const toast = useToast();
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ['templates'], queryFn: () => api<Template[]>('/templates/') });
  const fields = useFields();
  const known = (fields.data ?? []).map(f => f.key);
  const label = (k: string) => fields.data?.find(f => f.key === k)?.label ?? k;
  const [edit, setEdit] = useState<Partial<Template> | null>(null);

  const save = useMutation({
    mutationFn: (t: Partial<Template>) =>
      api<Template>(t.id ? `/templates/${t.id}/` : '/templates/', { method: t.id ? 'PATCH' : 'POST', body: { title: t.title, body: t.body } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['templates'] }); setEdit(null); toast('Template saved'); },
    onError: (e: Error) => toast(e.message, 'bad'),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/templates/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  });

  return (
    <>
      <section className="panel">
        <div className="row spread">
          <h2>{edit ? (edit.id ? 'Edit template' : 'New template') : 'Your templates'}</h2>
          {!edit && <button type="button" className="primary" onClick={() => setEdit({ title: '', body: `Hello ${NAME_TAG},\n\n` })}>New template</button>}
        </div>
        {edit && <Editor value={edit} onChange={setEdit} busy={save.isPending} onSave={() => save.mutate(edit)} onCancel={() => setEdit(null)} />}
        {!edit && !data?.length && <Empty>No templates yet. Create one here, or save a message from New broadcast.</Empty>}
      </section>

      {!!data?.length && (
        <div className="cards">
          {data.map(t => (
            <div key={t.id} className="card">
              <div className="row spread">
                <span className="name">{t.title} <SharedTag by={t.shared_by} /></span>
                <span className="row" style={{ gap: 4 }}>
                  {usesName(t.body) && <Pill tone="ok" title="Each recipient sees their own name">Name</Pill>}
                  {usedFields(t.body, known).map(k => <Pill key={k} tone="ok" title={`Each recipient sees their own ${label(k)}`}>{label(k)}</Pill>)}
                </span>
              </div>
              <Bubble text={t.body} sample={sampleFor(fields.data)} known={known} />
              <span className="small">Updated {dateTime(t.updated_at)}</span>
              <div className="row">
                <button type="button" className="primary" onClick={() => nav(`/compose?template=${t.id}`)}>Send</button>
                {!t.shared_by && (<>
                  <button type="button" className="ghost" onClick={() => { setEdit(t); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Edit</button>
                  <ConfirmButton confirm="Delete?" onConfirm={() => remove.mutateAsync(t.id)}>Delete</ConfirmButton>
                </>)}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function Editor({ value, onChange, busy, onSave, onCancel }: {
  value: Partial<Template>; onChange: (t: Partial<Template>) => void; busy: boolean; onSave: () => void; onCancel: () => void;
}) {
  const textRef = useRef<HTMLTextAreaElement>(null);
  const body = value.body ?? '';
  const [sample, setSample] = useState('Rahim');
  const [values, setValues] = useState<Record<string, string>>({});
  const fields = useFields();
  const known = (fields.data ?? []).map(f => f.key);
  const used = usedFields(body, known);
  return (
    <form className="grid-2" onSubmit={(e: FormEvent) => { e.preventDefault(); onSave(); }}>
      <div className="stack">
        <label className="field"><span>Name</span>
          <input type="text" value={value.title ?? ''} maxLength={80} required placeholder="e.g. Eid offer"
            onChange={e => onChange({ ...value, title: e.target.value })} />
        </label>
        <FormatBar textRef={textRef} value={body} onChange={v => onChange({ ...value, body: v })} />
        <textarea ref={textRef} value={body} required maxLength={60000} aria-label="Template text"
          onChange={e => onChange({ ...value, body: e.target.value })} />
        <p className="small" style={{ margin: 0 }}>
          <b>+ Name</b> adds <code className="inline">{NAME_TAG}</code>: each recipient sees their own contact name there, and contacts
          without a name see the word after <code className="inline">|</code> (change "friend" to anything you like).
          <b> + Field</b> adds a column from your imported Excel/CSV, like <code className="inline">{'{score}'}</code>; add
          <code className="inline">{'|text'}</code> for people with no value, e.g. <code className="inline">{'{score|N/A}'}</code>.
          Import the data on the Contacts page and choose <b>Use in messages</b> for those columns.
        </p>
        <div className="row">
          <button className="primary" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save template'}</button>
          <button className="ghost" type="button" onClick={onCancel}>Cancel</button>
        </div>
      </div>
      <div className="stack">
        <span className="lbl">Preview</span>
        <Bubble text={body} sample={sampleFor(fields.data, sample, values)} known={known} />
        {(usesName(body) || used.length > 0) && (
          <div className="optgrid small">
            {usesName(body) && (<>
              <label htmlFor="pv-name">Name</label>
              <input id="pv-name" type="text" value={sample} onChange={e => setSample(e.target.value)} maxLength={60} style={{ maxWidth: 200 }}
                placeholder="(no name)" />
            </>)}
            {used.map(k => {
              const f = fields.data!.find(x => x.key === k)!;
              return (
                <span key={k} style={{ display: 'contents' }}>
                  <label htmlFor={`pv-${k}`}>{f.label}</label>
                  <input id={`pv-${k}`} type="text" value={values[k] ?? `‹${f.label}›`} maxLength={80} style={{ maxWidth: 200 }}
                    onChange={e => setValues({ ...values, [k]: e.target.value })} placeholder="(empty)" />
                </span>
              );
            })}
          </div>
        )}
        {(usesName(body) || used.length > 0) && <span className="small">Try sample values above to check how the message reads. Clear a box to see what people without that value get.</span>}
      </div>
    </form>
  );
}
