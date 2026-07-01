import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  Building2,
  ChevronRight,
  CircleAlert,
  ClipboardList,
  Crosshair,
  MapPin,
  MessageSquareText,
  NotebookPen,
  PhoneCall,
  Radar,
  SlidersHorizontal,
  Sparkles,
  Stethoscope,
  TrendingUp,
  X,
} from "lucide-react";
import { getRankedProviders, generateBrief, getNotes, addNote } from "./api";
import type { CrmNote, GenerationResponse, ProviderRanked } from "./types";

type FilterKey = "All" | "Warm" | "Interested" | "Neutral" | "No CRM";

const filters: FilterKey[] = ["All", "Warm", "Interested", "Neutral", "No CRM"];

type Weights = { w_volume: number; w_fit: number; w_engagement: number };

const DEFAULT_WEIGHTS: Weights = { w_volume: 20, w_fit: 40, w_engagement: 40 };

const WEIGHT_FIELDS: { key: keyof Weights; label: string }[] = [
  { key: "w_volume", label: "Volume" },
  { key: "w_fit", label: "Product fit" },
  { key: "w_engagement", label: "Engagement" },
];

const toneClass: Record<string, string> = {
  Warm: "is-warm",
  Interested: "is-interested",
  Neutral: "is-neutral",
};

function getSentiment(crmScore: number | null, hasCrmData: boolean): string {
  if (!hasCrmData) {
    return "No CRM";
  }
  if (crmScore === null) {
    return "Neutral";
  }
  if (crmScore >= 70) {
    return "Warm";
  }
  if (crmScore >= 40) {
    return "Interested";
  }
  return "Neutral";
}

export function App() {
  const [providers, setProviders] = useState<ProviderRanked[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeProduct, setActiveProduct] = useState<string>("xT CDx");
  const [activeFilter, setActiveFilter] = useState<FilterKey>("All");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [generatedBriefs, setGeneratedBriefs] = useState<Record<string, GenerationResponse>>({});
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [showWeights, setShowWeights] = useState(false);
  const [notesByProvider, setNotesByProvider] = useState<Record<string, CrmNote[]>>({});
  const [showNotes, setShowNotes] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");
  const [isSavingNote, setIsSavingNote] = useState(false);
  const hasLoaded = useRef(false);

  useEffect(() => {
    let canceled = false;
    if (hasLoaded.current) {
      setRefreshing(true);
    }
    const handle = setTimeout(
      () => {
        getRankedProviders(weights)
          .then((items) => {
            if (canceled) return;
            setProviders(items);
            setSelectedId((prev) =>
              prev && items.some((item) => item.provider_id === prev)
                ? prev
                : items[0]?.provider_id ?? null,
            );
          })
          .catch((err) => {
            if (!canceled) setError(err.message ?? "Unable to load providers");
          })
          .finally(() => {
            if (canceled) return;
            setLoading(false);
            setRefreshing(false);
            hasLoaded.current = true;
          });
      },
      hasLoaded.current ? 250 : 0,
    );
    return () => {
      canceled = true;
      clearTimeout(handle);
    };
  }, [weights]);

  const weightTotal = weights.w_volume + weights.w_fit + weights.w_engagement;
  const weightPct = (value: number) => (weightTotal ? Math.round((value / weightTotal) * 100) : 0);
  const isDefaultWeights =
    weights.w_volume === DEFAULT_WEIGHTS.w_volume &&
    weights.w_fit === DEFAULT_WEIGHTS.w_fit &&
    weights.w_engagement === DEFAULT_WEIGHTS.w_engagement;

  const weightsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showWeights) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (weightsRef.current && !weightsRef.current.contains(event.target as Node)) {
        setShowWeights(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowWeights(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [showWeights]);

  useEffect(() => {
    if (!showNotes) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowNotes(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [showNotes]);

  const selected = useMemo(
    () => providers.find((provider) => provider.provider_id === selectedId) ?? providers[0] ?? null,
    [providers, selectedId],
  );

  useEffect(() => {
    if (!selected) {
      return;
    }
    if (!selected.products.includes(activeProduct)) {
      setActiveProduct(selected.best_fit_product || selected.products[0] || "xT CDx");
    }
  }, [selected, activeProduct]);

  const filteredProviders = useMemo(
    () =>
      providers.filter((provider) => {
        if (activeFilter === "All") return true;
        if (activeFilter === "No CRM") return provider.crm.has_crm_data === false;
        return getSentiment(provider.crm.crm_score, provider.crm.has_crm_data) === activeFilter;
      }),
    [providers, activeFilter],
  );

  const generated = selected ? generatedBriefs[selected.provider_id] : undefined;
  // Spinner state is per-provider so a canceled/stale generation for one account
  // can never strand the button on another account (see prior "stuck Generating…").
  const isGenerating = selected ? generatingId === selected.provider_id : false;
  const selectedNotes = selected ? notesByProvider[selected.provider_id] ?? [] : [];

  // Auto-load the call brief for the selected account so speaking notes are
  // always populated without a manual click.
  useEffect(() => {
    if (!selected || generatedBriefs[selected.provider_id]) {
      return;
    }
    let canceled = false;
    const providerId = selected.provider_id;
    setGeneratingId(providerId);
    generateBrief(providerId)
      .then((payload) => {
        if (!canceled) setGeneratedBriefs((state) => ({ ...state, [providerId]: payload }));
      })
      .catch((err) => {
        if (!canceled) setError((err as Error).message ?? "Unable to generate brief");
      })
      .finally(() => {
        // Clear unconditionally (even if this run was canceled) so a stale
        // generation can't strand the spinner; only clear if it's still ours.
        setGeneratingId((current) => (current === providerId ? null : current));
      });
    return () => {
      canceled = true;
    };
  }, [selected, generatedBriefs]);

  useEffect(() => {
    if (!selected || notesByProvider[selected.provider_id]) {
      return;
    }
    let canceled = false;
    const providerId = selected.provider_id;
    getNotes(providerId)
      .then((notes) => {
        if (!canceled) setNotesByProvider((state) => ({ ...state, [providerId]: notes }));
      })
      .catch(() => undefined);
    return () => {
      canceled = true;
    };
  }, [selected, notesByProvider]);

  const handleGenerateBrief = async () => {
    if (!selected) return;
    const providerId = selected.provider_id;
    setGeneratingId(providerId);
    try {
      const payload = await generateBrief(providerId);
      setGeneratedBriefs((state) => ({ ...state, [providerId]: payload }));
    } catch (err) {
      setError((err as Error).message ?? "Unable to generate brief");
    } finally {
      setGeneratingId((current) => (current === providerId ? null : current));
    }
  };

  const handleSaveNote = async () => {
    if (!selected || !noteDraft.trim()) return;
    setIsSavingNote(true);
    const providerId = selected.provider_id;
    try {
      const notes = await addNote(providerId, noteDraft.trim());
      setNotesByProvider((state) => ({ ...state, [providerId]: notes }));
      setNoteDraft("");
    } catch (err) {
      setError((err as Error).message ?? "Unable to save note");
    } finally {
      setIsSavingNote(false);
    }
  };

  if (loading) {
    return (
      <main className="app-shell">
        <div className="loading-state">Loading providers…</div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="app-shell">
        <div className="error-state">{error}</div>
      </main>
    );
  }

  if (!selected) {
    return (
      <main className="app-shell">
        <div className="error-state">No providers available.</div>
      </main>
    );
  }

  const activeReasons = selected.product_fit_reasons[activeProduct] ?? [selected.signal];
  const concern = selected.crm.top_objection ?? (selected.crm.has_crm_data ? "CRM opportunity" : "No CRM history");
  const sentiment = getSentiment(selected.crm.crm_score, selected.crm.has_crm_data);

  return (
    <main className="app-shell">
      <section className="command-bar">
        <div>
          <div className="eyebrow">
            <Radar size={15} />
            Oncology Sales Intelligence
          </div>
          <h1>Prioritize the next conversation.</h1>
        </div>
        <div className="command-actions">
          <div className="weights-anchor" ref={weightsRef}>
            <button
              className={`ghost-button ${showWeights ? "is-active" : ""}`}
              type="button"
              onClick={() => setShowWeights((open) => !open)}
              aria-expanded={showWeights}
              title="Adjust how the priority queue is ranked"
            >
              <SlidersHorizontal size={16} />
              Weights
              <span className="weights-chip">
                {weightPct(weights.w_volume)}/{weightPct(weights.w_fit)}/{weightPct(weights.w_engagement)}
              </span>
            </button>
            {showWeights ? (
              <div className="weights-popover" role="group" aria-label="Ranking weights">
                <div className="weights-header">
                  <span>Ranking weights</span>
                  <button
                    type="button"
                    onClick={() => setWeights(DEFAULT_WEIGHTS)}
                    disabled={isDefaultWeights}
                  >
                    Reset
                  </button>
                </div>
                <p className="weights-subhead">
                  Balance how accounts are prioritized. Values normalize to 100%.
                </p>
                {WEIGHT_FIELDS.map(({ key, label }) => (
                  <div className="weight-row" key={key}>
                    <div className="weight-label">
                      <span>{label}</span>
                      <strong>{weightPct(weights[key])}%</strong>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={weights[key]}
                      aria-label={`${label} weight`}
                      onChange={(event) =>
                        setWeights((current) => ({ ...current, [key]: Number(event.target.value) }))
                      }
                    />
                  </div>
                ))}
                <p className={`weights-status ${refreshing ? "is-busy" : ""}`}>
                  {refreshing ? "Re-ranking queue…" : "Queue updates as you adjust."}
                </p>
              </div>
            ) : null}
          </div>
          <button className="primary-button" type="button" onClick={handleGenerateBrief} disabled={isGenerating}>
            <Sparkles size={16} />
            {isGenerating ? "Generating…" : "Generate Brief"}
          </button>
        </div>
      </section>

      <section className="workspace-grid">
        <aside className="priority-panel panel">
          <div className="panel-heading">
            <div>
              <p>Priority Queue</p>
              <h2>Target Accounts</h2>
            </div>
            <span>{filteredProviders.length} providers</span>
          </div>

          <div className="filter-row" aria-label="Provider filters">
            {filters.map((filter) => (
              <button
                key={filter}
                className={activeFilter === filter ? "is-active" : ""}
                type="button"
                onClick={() => setActiveFilter(filter)}
              >
                {filter}
              </button>
            ))}
          </div>

          <div className="queue-list">
            {filteredProviders.map((provider, index) => {
              const cardSentiment = getSentiment(provider.crm.crm_score, provider.crm.has_crm_data);
              const cardConcern = provider.crm.top_objection ?? (provider.crm.has_crm_data ? "CRM opportunity" : "No CRM history");
              return (
                <button
                  key={provider.provider_id}
                  type="button"
                  className={`provider-card ${provider.provider_id === selected.provider_id ? "is-selected" : ""}`}
                  onClick={() => setSelectedId(provider.provider_id)}
                >
                  <div className="rank-block">
                    <span>#{index + 1}</span>
                    <strong>{Math.round(provider.score)}</strong>
                  </div>
                  <div className="provider-card-body">
                    <div className="provider-title-row">
                      <h3>{provider.name}</h3>
                      <ChevronRight size={17} />
                    </div>
                    <p>{provider.specialty}</p>
                    <div className="provider-meta">
                      <span>
                        <Building2 size={13} />
                        {provider.institution}
                      </span>
                      <span>
                        <MapPin size={13} />
                        {provider.region}
                      </span>
                    </div>
                    <div className="card-footer">
                      <span className={`sentiment-pill ${toneClass[cardSentiment] ?? ""}`}>{cardSentiment}</span>
                      <span>{cardConcern}</span>
                    </div>
                    {!provider.crm.has_crm_data ? <span className="crm-badge">No CRM history</span> : null}
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="brief-panel panel">
          <div className="account-hero">
            <div>
              <div className="eyebrow compact">
                <Crosshair size={14} />
                Selected Account
              </div>
              <h2>{selected.name}</h2>
              <p>
                {selected.specialty} at {selected.institution}
              </p>
              <button className="note-button" type="button" onClick={() => setShowNotes(true)}>
                <NotebookPen size={15} />
                Log CRM note
                {selectedNotes.length > 0 ? <span className="note-count">{selectedNotes.length}</span> : null}
              </button>
            </div>
            <div className="priority-orb" aria-label={`Priority score ${Math.round(selected.score)}`}>
              <span>{Math.round(selected.score)}</span>
              <small>priority</small>
            </div>
          </div>

          <div className="metric-strip">
            <MetricCard icon={<Activity size={18} />} label="Monthly patients" value={selected.monthly_patients} />
            <MetricCard icon={<TrendingUp size={18} />} label="Addressable / mo" value={selected.addressable_patients_per_month} />
            <MetricCard
              icon={<Stethoscope size={18} />}
              label="Testing fit"
              value={selected.pct_biomarker_tested != null ? `${selected.pct_biomarker_tested}%` : "N/A"}
            />
            <MetricCard
              icon={<ClipboardList size={18} />}
              label="CRM score"
              value={selected.crm.crm_score != null ? selected.crm.crm_score : "N/A"}
            />
          </div>

          <div className="brief-content-grid">
            <section className="insight-card why-score-card">
              <div className="why-copy">
                <div className="section-title">
                  <CircleAlert size={16} />
                  Why This Account
                </div>
                <ul className="fit-list">
                  {selected.fit_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>

              <div className="score-module">
                <div className="section-title">
                  <BarChart3 size={16} />
                  Score Composition
                </div>
                <div className="score-bars">
                  {selected.score_components.map((item) => (
                    <div className="score-row" key={item.label}>
                      <div>
                        <span>{item.label}</span>
                        <strong>{Math.round(item.value)}</strong>
                      </div>
                      <div className="bar-track">
                        <span style={{ width: `${Math.round(item.value)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="insight-card">
              <div className="section-title">
                <Sparkles size={16} />
                Product Fit
              </div>
              <p className="product-note">
                Ranked by fit for {selected.specialty}. Select one to see the rationale.
              </p>
              <div className="product-rank">
                {selected.products.map((product) => {
                  const fitScore = selected.product_fit[product as keyof typeof selected.product_fit] ?? 0;
                  const isBest = product === selected.best_fit_product;
                  return (
                    <button
                      key={product}
                      type="button"
                      className={`product-rank-row ${activeProduct === product ? "is-active" : ""}`}
                      onClick={() => setActiveProduct(product)}
                    >
                      <div className="product-rank-head">
                        <span className="product-rank-name">
                          {product}
                          {isBest ? (
                            <span className="best-fit-badge">
                              <BadgeCheck size={12} />
                              Best fit
                            </span>
                          ) : null}
                        </span>
                        <strong>{fitScore}</strong>
                      </div>
                      <div className="bar-track">
                        <span style={{ width: `${fitScore}%` }} />
                      </div>
                    </button>
                  );
                })}
              </div>
              <div className="product-rationale">
                <span>Why {activeProduct} fits</span>
                <ul>
                  {activeReasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            </section>
          </div>
        </section>

        <section className="prep-panel panel">
          <div className="panel-heading prep-heading">
            <div>
              <p>Call Prep</p>
              <h2>Meeting Brief</h2>
            </div>
            <PhoneCall size={18} />
          </div>

          <article className="elevator-card">
            <div className="question-topline">
              <span>Elevator Pitch</span>
              <Sparkles size={16} />
            </div>
            <h3>{generated?.meeting_script.headline ?? selected.signal}</h3>
            <div className="static-notes">
              {(generated?.meeting_script.bullets ?? [
                `Lead with ${selected.specialty} volume and biomarker workflow urgency.`,
                `Tie the recommendation to ${selected.crm.key_interest ?? "speed and clinical confidence"}.`,
              ]).map((note, index) => (
                <p key={index}>{note}</p>
              ))}
            </div>
          </article>

          <div className="prep-subhead">
            <MessageSquareText size={15} />
            Likely Questions
          </div>

          <div className="question-stack">
            {(generated?.likely_questions ?? [
              {
                question: selected.crm.top_objection ?? "How will this fit into my current workflow?",
                intent: selected.crm.key_interest ?? "Openness",
                answerBullets: [
                  selected.crm.reasoning ?? "Use this as a chance to connect product fit to current clinical priorities.",
                ],
              },
            ]).map((question, index) => (
              <article className="question-card" key={`${question.intent}-${index}`}>
                <div className="question-topline">
                  <span>{question.intent}</span>
                  <MessageSquareText size={16} />
                </div>
                <h3>{question.question}</h3>
                <div className="answer-block">
                  <span>Speaking notes</span>
                  <div className="static-notes">
                    {question.answerBullets.map((note, noteIndex) => (
                      <p key={noteIndex}>{note}</p>
                    ))}
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="next-step-card">
            <div>
              <span>Suggested close</span>
              <p>{generated?.meeting_script.suggested_close ?? "Ask for one recent case where current testing speed or tissue access delayed a treatment decision."}</p>
            </div>
            <ArrowRight size={18} />
          </div>
        </section>
      </section>

      {showNotes ? (
        <div className="modal-overlay" onMouseDown={() => setShowNotes(false)}>
          <div
            className="notes-modal"
            role="dialog"
            aria-modal="true"
            aria-label={`CRM notes for ${selected.name}`}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="notes-modal-head">
              <div>
                <div className="eyebrow compact">
                  <NotebookPen size={13} />
                  CRM Note
                </div>
                <h3>{selected.name}</h3>
              </div>
              <button className="icon-button" type="button" onClick={() => setShowNotes(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>

            <div className="notes-history">
              {selectedNotes.length === 0 ? (
                <p className="notes-empty">No notes logged yet. Add the first one below.</p>
              ) : (
                selectedNotes
                  .slice()
                  .reverse()
                  .map((note) => (
                    <div className="note-item" key={note.timestamp}>
                      <div className="note-item-head">
                        <span>{note.author}</span>
                        <time>{formatTimestamp(note.timestamp)}</time>
                      </div>
                      <p>{note.text}</p>
                    </div>
                  ))
              )}
            </div>

            <textarea
              className="note-input"
              placeholder="Log a call summary, objection, or next step. This writes to the CRM record and refines this account's score on the next refresh."
              value={noteDraft}
              onChange={(event) => setNoteDraft(event.target.value)}
              rows={3}
            />
            <div className="notes-modal-actions">
              <button className="ghost-button" type="button" onClick={() => setShowNotes(false)}>
                Close
              </button>
              <button
                className="primary-button"
                type="button"
                onClick={handleSaveNote}
                disabled={isSavingNote || !noteDraft.trim()}
              >
                {isSavingNote ? "Saving…" : "Save to CRM"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <div className="metric-card">
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
