import { forwardRef, useEffect, useId, useState, type KeyboardEvent } from 'react';
import { corDoTipo, rotuloDoTipo } from '../constants';
import { titleCase } from '../format';
import { Icon } from './Icon';

export interface SearchBuilding {
  id: string;
  endereco: string | null;
  bairro: string | null;
  estabelecimento: string | null;
  tipo: string;
  lng: number;
  lat: number;
}

export interface SearchBairro {
  bairro: string;
  total: number;
  lng: number;
  lat: number;
}

export type SearchPick =
  | { kind: 'building'; item: SearchBuilding }
  | { kind: 'bairro'; item: SearchBairro };

interface Props {
  apiUrl: string;
  onPick: (pick: SearchPick) => void;
  onFocusChange?: (focused: boolean) => void;
}

const DEBOUNCE_MS = 200;

export const SearchBox = forwardRef<HTMLInputElement, Props>(function SearchBox({ apiUrl, onPick, onFocusChange }, ref) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<{ query: string; buildings: SearchBuilding[]; bairros: SearchBairro[] } | null>(null);
  const [failedQuery, setFailedQuery] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const listId = useId();

  const trimmed = query.trim();
  useEffect(() => {
    if (trimmed.length < 2) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(`${apiUrl}/api/search?${new URLSearchParams({ q: trimmed, limit: '8' })}`, { signal: controller.signal })
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then((data) => {
          setResults({ query: trimmed, buildings: data.buildings ?? [], bairros: data.bairros ?? [] });
          setFailedQuery(null);
          setActive(0);
        })
        .catch((err) => {
          if (!controller.signal.aborted) setFailedQuery(trimmed);
          void err;
        });
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [apiUrl, trimmed]);

  const current = trimmed.length >= 2 && results?.query === trimmed ? results : null;
  const loading = trimmed.length >= 2 && !current && failedQuery !== trimmed;
  const picks: SearchPick[] = current
    ? [
        ...current.bairros.map((item) => ({ kind: 'bairro' as const, item })),
        ...current.buildings.map((item) => ({ kind: 'building' as const, item })),
      ]
    : [];

  const pick = (choice: SearchPick) => {
    onPick(choice);
    setQuery('');
    setResults(null);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' && picks.length) {
      event.preventDefault();
      setActive((i) => (i + 1) % picks.length);
    } else if (event.key === 'ArrowUp' && picks.length) {
      event.preventDefault();
      setActive((i) => (i - 1 + picks.length) % picks.length);
    } else if (event.key === 'Enter' && picks[active]) {
      event.preventDefault();
      pick(picks[active]);
    } else if (event.key === 'Escape') {
      if (query) {
        event.stopPropagation();
        setQuery('');
      } else {
        event.currentTarget.blur();
      }
    }
  };

  const open = trimmed.length >= 2;
  return (
    <div className="search">
      <div className="search-field">
        <Icon name="search" size={18} className="search-icon" />
        <input
          ref={ref}
          type="search"
          inputMode="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="Buscar endereço, comércio ou bairro"
          aria-label="Buscar endereço, comércio ou bairro"
          role="combobox"
          aria-expanded={open && picks.length > 0}
          aria-controls={listId}
          aria-activedescendant={picks.length ? `${listId}-${active}` : undefined}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => onFocusChange?.(true)}
          onBlur={() => onFocusChange?.(false)}
        />
        {loading && <span className="spinner" aria-label="Buscando" />}
        {query && !loading && (
          <button type="button" className="icon-button tiny" aria-label="Limpar busca" onClick={() => setQuery('')}>
            <Icon name="close" size={14} />
          </button>
        )}
        <kbd className="search-kbd" aria-hidden="true">/</kbd>
      </div>

      {open && (
        <div className="search-results" id={listId} role="listbox" aria-label="Resultados da busca">
          {failedQuery === trimmed && <p className="muted pad">Não foi possível buscar agora.</p>}
          {current && picks.length === 0 && <p className="muted pad">Nada encontrado para “{trimmed}”.</p>}
          {current && current.bairros.length > 0 && <h3 className="section-label">Bairros</h3>}
          {picks.map((choice, index) => {
            const isFirstBuilding = choice.kind === 'building' && index === current!.bairros.length;
            return (
              <div key={choice.kind === 'bairro' ? `b:${choice.item.bairro}` : choice.item.id}>
                {isFirstBuilding && <h3 className="section-label">Endereços e comércios</h3>}
                <button
                  type="button"
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  className={`result-row${index === active ? ' active' : ''}`}
                  onMouseEnter={() => setActive(index)}
                  // mousedown: o clique chega antes de o campo perder o foco.
                  onMouseDown={(event) => {
                    event.preventDefault();
                    pick(choice);
                  }}
                >
                  {choice.kind === 'bairro' ? (
                    <>
                      <span className="result-icon"><Icon name="map" size={16} /></span>
                      <span className="result-text">
                        <strong>{titleCase(choice.item.bairro)}</strong>
                        <span className="muted">{choice.item.total.toLocaleString('pt-BR')} endereços</span>
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="result-icon" style={{ color: corDoTipo(choice.item.tipo) }}><Icon name="pin" size={16} /></span>
                      <span className="result-text">
                        <strong>{titleCase(choice.item.estabelecimento || choice.item.endereco)}</strong>
                        <span className="muted">
                          {[choice.item.estabelecimento ? titleCase(choice.item.endereco) : null, titleCase(choice.item.bairro), rotuloDoTipo(choice.item.tipo)]
                            .filter(Boolean).join(' · ')}
                        </span>
                      </span>
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});
