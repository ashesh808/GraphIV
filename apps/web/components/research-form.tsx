"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { activeJob, validJobId, type ResearchEffort, type ResearchJob, type ResearchMode } from "@/lib/research";
import { Icon } from "./icon";

const STORAGE_KEY = "graphiv.latestResearchJob";
const POLL_MS = 3_000;
const MAX_POLLS = 360;
const modes: { value: ResearchMode; label: string; description: string }[] = [
  { value: "survey", label: "Survey", description: "Map the literature around your question." },
  { value: "frontier", label: "Frontier", description: "Explore emerging work and open questions." },
  { value: "consensus", label: "Consensus", description: "Compare evidence and agreement across papers." },
  { value: "ancestry", label: "Ancestry", description: "Trace the work and ideas a field builds on." },
  { value: "evolution", label: "Evolution", description: "Follow how approaches have changed over time." },
];
const stageDescriptions = {
  starting: "Preparing the research run.",
  retrieving: "Retrieving papers for this question.",
  mining: "Examining citation connections between papers.",
  reading_papers: "Reading the relevant papers and collecting evidence.",
  composing_report: "Writing a report grounded in the selected papers.",
  publishing_report: "Saving the report and its supporting artifacts.",
  complete: "The report has been saved.",
  failed: "The run stopped before a report could be saved.",
};

function storeJob(id: string | null) {
  try { if (id) sessionStorage.setItem(STORAGE_KEY, id); else sessionStorage.removeItem(STORAGE_KEY); } catch { /* Research also works without browser storage. */ }
}

async function jobResponse(response: Response): Promise<ResearchJob> {
  const body = await response.json();
  if (!response.ok) {
    const reasons = Array.isArray(body.reasons) ? body.reasons.filter((reason: unknown) => typeof reason === "string").join(" ") : "";
    throw new Error([typeof body.error === "string" ? body.error : "The request could not be completed.", reasons].filter(Boolean).join(" "));
  }
  if (!body || !validJobId(body.id) || !["queued", "running", "complete", "failed"].includes(body.status)) throw new Error("The server returned an invalid research status. Please check again.");
  return body as ResearchJob;
}

export function ResearchForm() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<ResearchMode>("survey");
  const [effort, setEffort] = useState<ResearchEffort>("standard");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [job, setJob] = useState<ResearchJob | null>(null);
  const [trackedId, setTrackedId] = useState<string | null>(null);
  const [pollError, setPollError] = useState("");
  const [checking, setChecking] = useState(false);
  const [checkVersion, setCheckVersion] = useState(0);
  const completed = useRef<string | null>(null);
  const submitInFlight = useRef(false);
  const questionField = useRef<HTMLTextAreaElement>(null);
  const busy = submitting || Boolean(trackedId && (!job || activeJob(job)));

  useEffect(() => {
    try {
      const id = sessionStorage.getItem(STORAGE_KEY);
      if (id && validJobId(id)) setTrackedId(id);
    } catch { /* A new submission can still be made without browser storage. */ }
  }, []);

  useEffect(() => {
    if (!trackedId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    let stopped = false;
    async function poll() {
      setChecking(true);
      try {
        const next = await jobResponse(await fetch(`/api/jobs/${trackedId}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]) }));
        if (stopped) return;
        setJob(next);
        setPollError("");
        if (next.status === "complete" && completed.current !== next.id) {
          completed.current = next.id;
          router.refresh();
        }
        if (activeJob(next)) {
          attempts += 1;
          if (attempts < MAX_POLLS) timer = setTimeout(poll, document.hidden ? 10_000 : POLL_MS);
          else setPollError("This research is taking longer than usual. Check progress when you’re ready; the run continues on the server.");
        }
      } catch (error) {
        if (!stopped) setPollError(error instanceof Error && !(error instanceof TypeError) && !(error instanceof DOMException) ? error.message : "Progress could not be checked. Your research may still be running. Please check again.");
      } finally {
        if (!stopped) setChecking(false);
      }
    }
    void poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [trackedId, checkVersion, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitInFlight.current || busy) return;
    if (!question.trim()) { questionField.current?.focus(); return; }
    submitInFlight.current = true;
    setSubmitting(true);
    setSubmitError("");
    try {
      const next = await jobResponse(await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), mode, effort }),
        signal: AbortSignal.timeout(15_000),
      }));
      setJob(next);
      setPollError("");
      setTrackedId(next.id);
      storeJob(next.id);
    } catch (error) {
      setSubmitError(error instanceof Error && !(error instanceof TypeError) && !(error instanceof DOMException) ? error.message : "Submission could not be confirmed. Check the library before trying again.");
    } finally {
      setSubmitting(false);
      submitInFlight.current = false;
    }
  }

  function dismiss() {
    storeJob(null);
    setTrackedId(null);
    setJob(null);
    setPollError("");
    questionField.current?.focus();
  }

  const modeDescription = modes.find((item) => item.value === mode)?.description;
  const statusTitle = !job ? "Checking your research" : { queued: "Research queued", running: "Research in progress", complete: "Report ready", failed: "Research could not be completed" }[job.status];

  return <section className="research-composer" aria-labelledby="research-title">
    <div className="composer-heading"><h2 id="research-title">Ask a research question</h2><p>Start with a focused question. Follow the evidence into a report.</p></div>
    <form onSubmit={submit} className="research-form">
      <label htmlFor="research-question" className="sr-only">Research question</label>
      <textarea ref={questionField} id="research-question" name="question" rows={2} maxLength={4_000} required disabled={busy} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What does the evidence say about…" aria-describedby={submitError ? "research-submit-error" : "research-mode-description"} />
      <div className="composer-toolbar">
        <div className="composer-options">
          <label className="composer-select"><span>Mode</span><select name="mode" aria-label="Research mode" disabled={busy} value={mode} onChange={(event) => setMode(event.target.value as ResearchMode)}>{modes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><Icon name="chevron" width="14" height="14" /></label>
          <span className="composer-option-divider" aria-hidden="true" />
          <label className="composer-select"><span>Depth</span><select name="effort" aria-label="Research depth" disabled={busy} value={effort} onChange={(event) => setEffort(event.target.value as ResearchEffort)}><option value="quick">Quick</option><option value="standard">Standard</option><option value="deep">Deep</option></select><Icon name="chevron" width="14" height="14" /></label>
        </div>
        <button className="button-primary research-submit" disabled={busy || !question.trim()} type="submit">{submitting ? <><Icon name="refresh" width="15" height="15" className="spinning" />Submitting…</> : <>Start research<Icon name="arrow" width="16" height="16" /></>}</button>
      </div>
      <p className="composer-help" id="research-mode-description">{modeDescription}</p>
      {submitError && <p id="research-submit-error" className="research-error" role="alert">{submitError}</p>}
    </form>
    {trackedId && <div className={`research-progress ${job?.status === "failed" ? "research-progress-failed" : ""}`}>
      <div className="progress-symbol" aria-hidden="true"><Icon name={job?.status === "complete" ? "document" : job?.status === "failed" ? "close" : "refresh"} width="19" height="19" className={!pollError && (!job || activeJob(job)) ? "spinning" : ""} /></div>
      <div className="progress-copy">
        <p className="progress-title" role="status" aria-live="polite">{statusTitle}</p>
        {job && <p className="progress-question">{job.question}</p>}
        <p className="progress-detail" aria-live="polite" aria-atomic="true">{!job ? "Checking the last job saved in this browser tab." : job.status === "complete" ? `${job.result?.papers ?? 0} papers · ${job.mode} · ${job.effort} depth` : job.status === "failed" ? job.error || "The run stopped before a report could be saved. Try the question again." : job.status === "queued" ? "Waiting for the current run to finish. You can leave this page and check back." : `${job.stage ? stageDescriptions[job.stage] : "Retrieving papers, examining their connections, and writing the report."} You can leave this page and check back.`}</p>
        {pollError && <p className="research-error" role="alert">{pollError}</p>}
      </div>
      <div className="progress-actions">
        {job?.status === "complete" && job.result && <Link className="button-primary" href={`/runs/${encodeURIComponent(job.result.slug)}`}>Open report<Icon name="arrow" width="15" height="15" /></Link>}
        {pollError && <button type="button" className="button-secondary" disabled={checking} onClick={() => setCheckVersion((value) => value + 1)}><Icon name="refresh" width="14" height="14" className={checking ? "spinning" : ""} />{checking ? "Checking…" : "Check progress"}</button>}
        {((job && !activeJob(job)) || pollError) && <button className="text-button" type="button" onClick={dismiss}>{job?.status === "failed" ? "Try another question" : pollError ? "Dismiss status" : "Dismiss"}</button>}
      </div>
    </div>}
  </section>;
}
