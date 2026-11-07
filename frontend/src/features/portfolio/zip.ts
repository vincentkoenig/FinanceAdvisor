// ZIP-Archive der Bank im Browser entpacken: FinTrack bekommt nur die einzelnen PDFs und CSVs.
// Die Bibliothek wird erst beim ersten ZIP geladen, damit sie den Start der App nicht vergrößert.

const MAX_FILES = 500;
const MAX_BYTES = 300 * 1024 * 1024;

export const isZip = (file: File) => /\.zip$/i.test(file.name) || file.type === 'application/zip';

/** Dateien aus dem Archiv, nach Name sortiert; Ordner und Systemdateien bleiben draußen */
export async function filesFromZip(zip: File): Promise<File[]> {
  const { unzipSync } = await import('fflate');
  const data = new Uint8Array(await zip.arrayBuffer());
  let total = 0;
  let found = 0;
  let entries: Record<string, Uint8Array>;
  try {
    entries = unzipSync(data, {
      filter: ({ name, originalSize }) => {
        const wanted = /\.(pdf|csv)$/i.test(name) && !/(^|\/)(__MACOSX|\.)/.test(name);
        if (!wanted) return false;
        found += 1;
        total += originalSize;
        if (found > MAX_FILES) throw new RangeError(`Höchstens ${MAX_FILES} Dateien pro ZIP.`);
        if (total > MAX_BYTES) throw new RangeError('Das ZIP ist entpackt zu groß.');
        return true;
      },
    });
  } catch (failure) {
    throw new Error(failure instanceof RangeError ? failure.message : 'Das ZIP ließ sich nicht öffnen.', { cause: failure });
  }
  const files = Object.entries(entries)
    .sort(([a], [b]) => a.localeCompare(b, 'de'))
    .map(([name, content]) => new File([content.slice()], name.split('/').pop()!, {
      type: /\.pdf$/i.test(name) ? 'application/pdf' : 'text/csv',
    }));
  if (!files.length) throw new Error('Im ZIP liegen keine PDF- oder CSV-Dateien.');
  return files;
}
