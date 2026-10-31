// Kleiner Markdown-Leser für Antworten des KI-Beraters. Er baut React-Elemente statt HTML,
// darum kann aus einer Antwort nie Markup in die Seite gelangen. Kann: Absätze, Überschriften,
// Listen (auch nummeriert), Tabellen, **fett**, *kursiv*, `Code` und Links mit http(s).
import type { ReactNode } from 'react';

type Block =
  | { kind: 'p'; text: string }
  | { kind: 'h'; text: string }
  | { kind: 'ul' | 'ol'; items: string[] }
  | { kind: 'table'; head: string[]; rows: string[][] };

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_RULE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

const cells = (line: string) => line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());

export function parseBlocks(text: string): Block[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.length) blocks.push({ kind: 'p', text: paragraph.join(' ') });
    paragraph = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) { flush(); continue; }
    const heading = line.match(HEADING);
    if (heading) { flush(); blocks.push({ kind: 'h', text: heading[1] }); continue; }
    // Tabelle: Kopfzeile, Trennlinie, dann Zeilen
    if (TABLE_ROW.test(line) && TABLE_RULE.test(lines[i + 1] ?? '')) {
      flush();
      const head = cells(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && TABLE_ROW.test(lines[i])) rows.push(cells(lines[i++]));
      i--;
      blocks.push({ kind: 'table', head, rows });
      continue;
    }
    const bullet = line.match(BULLET), numbered = line.match(NUMBERED);
    if (bullet || numbered) {
      flush();
      const kind = bullet ? 'ul' : 'ol';
      const pattern = bullet ? BULLET : NUMBERED;
      const items: string[] = [];
      while (i < lines.length && pattern.test(lines[i])) items.push(lines[i++].match(pattern)![1]);
      i--;
      blocks.push({ kind, items });
      continue;
    }
    paragraph.push(line.trim());
  }
  flush();
  return blocks;
}

// Fett, kursiv, Code und Links innerhalb einer Zeile
const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|\*[^*\s][^*]*\*)/g;

export function inline(text: string): ReactNode[] {
  return text.split(INLINE).filter(Boolean).map((part, i) => {
    if (/^(\*\*|__).+(\*\*|__)$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (/^`.+`$/.test(part)) return <code key={i}>{part.slice(1, -1)}</code>;
    const link = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
    if (link) {
      return /^https?:\/\//.test(link[2])
        ? <a key={i} href={link[2]} target="_blank" rel="noopener noreferrer" className="link">{link[1]}</a>
        : link[1];
    }
    if (/^\*.+\*$/.test(part)) return <em key={i}>{part.slice(1, -1)}</em>;
    return part;
  });
}

export function Markdown({ text }: { text: string }) {
  return (
    <>
      {parseBlocks(text).map((block, i) => {
        switch (block.kind) {
          case 'h': return <p key={i} className="md-heading">{inline(block.text)}</p>;
          case 'p': return <p key={i}>{inline(block.text)}</p>;
          case 'ul': return <ul key={i}>{block.items.map((item, j) => <li key={j}>{inline(item)}</li>)}</ul>;
          case 'ol': return <ol key={i}>{block.items.map((item, j) => <li key={j}>{inline(item)}</li>)}</ol>;
          case 'table':
            return (
              <div className="table-wrap" key={i}>
                <table>
                  <thead><tr>{block.head.map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead>
                  <tbody>{block.rows.map((row, j) => <tr key={j}>{row.map((c, k) => <td key={k}>{inline(c)}</td>)}</tr>)}</tbody>
                </table>
              </div>
            );
        }
      })}
    </>
  );
}
