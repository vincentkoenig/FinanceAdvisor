// Chat mit dem KI-Berater. Frage der Seite: Was will ich über mein Geld wissen?
// Der Berater kennt Depot, Haushaltsbuch und Anlageprofil und ruft Live-Kurse ab (siehe chat/routes.py).
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useChatHistory, useSendMessage } from '../../api/advisor';
import { Icon } from '../../components/Icon';
import { Loaded } from '../../components/Loaded';
import { Markdown } from '../../lib/markdown';
import { useMoney } from '../../lib/privacy';

const SUGGESTIONS = [
  'Wie viel habe ich diesen Monat übrig?',
  'Wie ist mein Depot aufgeteilt?',
  'Was ist der Unterschied zwischen ETF und ETC?',
];

export function ChatPage() {
  const { text: mask } = useMoney();
  const history = useChatHistory();
  const send = useSendMessage();
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const pending = send.isPending ? send.variables : null;
  const count = (history.data?.length ?? 0) + (pending ? 1 : 0);

  // Neue Nachrichten unten sichtbar halten
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' });
  }, [count, send.isPending]);

  const ask = (message: string) => {
    const trimmed = message.trim();
    if (!trimmed || send.isPending) return;
    setError('');
    setText('');
    send.mutate(trimmed, {
      // Die Frage bleibt erhalten, damit sie sich noch einmal senden lässt
      onError: (e) => { setError(e.message); setText(trimmed); },
      onSettled: () => input.current?.focus(),
    });
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    ask(text);
  };

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Chat</h1>
          <p className="sub">Dein KI-Berater kennt Depot, Haushaltsbuch und Anlageprofil und ruft Live-Kurse ab</p>
        </div>
      </div>

      <section className="panel chat" aria-label="Unterhaltung">
        <div className="chat-scroll">
          <div className="chat-col" aria-live="polite">
            <Loaded queries={[history]}>
              {() => (
                <>
                  {history.data!.length === 0 && !pending && (
                    <p className="muted">Frag etwas zu deinem Depot oder deinen Ausgaben. Der Berater antwortet allgemein und gibt keine Kauf- oder Verkaufsempfehlungen.</p>
                  )}
                  {history.data!.map((entry, i) => (entry.role === 'user'
                    ? <div className="msg-user" key={i}>{mask(entry.message)}</div>
                    : <div className="msg-ai" key={i}><Markdown text={mask(entry.message)} /></div>))}
                  {pending && (
                    <>
                      <div className="msg-user">{pending}</div>
                      <div className="msg-ai typing" role="status" aria-label="Antwort wird geschrieben"><span /><span /><span /></div>
                    </>
                  )}
                </>
              )}
            </Loaded>
            <div ref={end} />
          </div>
        </div>
        <div className="composer-wrap">
          {error && <p className="err chat-error" role="alert">{error}</p>}
          {history.isSuccess && history.data.length === 0 && !pending && (
            <div className="suggest">
              {SUGGESTIONS.map((q) => <button key={q} className="btn btn-sm" onClick={() => ask(q)}>{q}</button>)}
            </div>
          )}
          <form className="composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="chat-input">Nachricht</label>
            <input id="chat-input" ref={input} placeholder="Nachricht an deinen Finanzberater" autoComplete="off" maxLength={4000}
              value={text} onChange={(e) => setText(e.target.value)} />
            <button className="btn btn-primary" type="submit" aria-label="Senden" disabled={send.isPending || !text.trim()}>
              <Icon name="send" size={16} />
            </button>
          </form>
        </div>
      </section>
    </>
  );
}
