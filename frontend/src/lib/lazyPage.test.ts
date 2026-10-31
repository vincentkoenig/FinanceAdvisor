import { afterEach, describe, expect, it, vi } from 'vitest';
import { load } from './lazyPage';

afterEach(() => sessionStorage.clear());

describe('Nachladen einer Seite', () => {
  it('lädt die Seite einmal neu, wenn die Datei nach einem Deploy fehlt', async () => {
    const reload = vi.fn();
    void load(() => Promise.reject(new Error('404')), reload);
    await vi.waitFor(() => expect(reload).toHaveBeenCalledOnce());
  });

  it('gibt beim zweiten Fehlschlag auf, statt endlos neu zu laden', async () => {
    sessionStorage.setItem('fintrack-chunk-reload', '1');
    const reload = vi.fn();
    await expect(load(() => Promise.reject(new Error('404')), reload)).rejects.toThrow('404');
    expect(reload).not.toHaveBeenCalled();
  });

  it('setzt die Sperre nach erfolgreichem Laden zurück', async () => {
    sessionStorage.setItem('fintrack-chunk-reload', '1');
    await expect(load(() => Promise.resolve('ok'))).resolves.toBe('ok');
    expect(sessionStorage.getItem('fintrack-chunk-reload')).toBeNull();
  });
});
