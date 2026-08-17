"use client";

import { useState } from "react";
import ResultView from "./ResultView";
import { tailorStream, type RunSummary } from "@/lib/api";

type Phase = "idle" | "running" | "done" | "error";

export default function TailorPanel({ candidateId }: { candidateId: string }) {
  const [jdText, setJdText] = useState("");
  const [jdUrl, setJdUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [log, setLog] = useState<string[]>([]);
  const [result, setResult] = useState<RunSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setPhase("running");
    setLog([]);
    setResult(null);
    setError(null);
    try {
      await tailorStream(
        candidateId,
        jdUrl.trim() ? { jd_url: jdUrl.trim() } : { jd_text: jdText },
        (e) => {
          if (e.type === "progress") setLog((l) => [...l, e.message]);
          else if (e.type === "result") {
            setResult(e);
            setPhase("done");
          } else {
            setError(e.message);
            setPhase("error");
          }
        }
      );
    } catch (e) {
      setError((e as Error).message);
      setPhase("error");
    }
  }

  return (
    <div className="space-y-5">
      {phase !== "done" && (
        <div className="space-y-3 rounded-xl border border-zinc-200 bg-white p-5">
          <label className="block text-sm font-medium text-zinc-700">
            粘贴 Job Description
          </label>
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            rows={10}
            disabled={phase === "running"}
            placeholder="把完整 JD 粘到这里…"
            className="w-full rounded-lg border border-zinc-300 p-3 text-sm focus:border-indigo-500 focus:outline-none disabled:bg-zinc-50"
          />
          <div className="flex items-center gap-3">
            <span className="text-xs text-zinc-400">或</span>
            <input
              value={jdUrl}
              onChange={(e) => setJdUrl(e.target.value)}
              disabled={phase === "running"}
              placeholder="JD 页面 URL（尽力抓取，很多站点反爬）"
              className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none disabled:bg-zinc-50"
            />
          </div>
          <button
            onClick={start}
            disabled={phase === "running" || (!jdText.trim() && !jdUrl.trim())}
            className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {phase === "running" ? "定制中…" : "开始定制"}
          </button>
        </div>
      )}

      {(phase === "running" || log.length > 0) && phase !== "done" && (
        <div className="space-y-2 rounded-xl border border-zinc-200 bg-white p-5">
          {log.map((m, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-zinc-700">
              {phase === "running" && i === log.length - 1 ? (
                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
              ) : (
                <span className="text-emerald-600">✓</span>
              )}
              {m}
            </div>
          ))}
          {phase === "running" && log.length === 0 && (
            <p className="text-sm text-zinc-400">连接中…</p>
          )}
        </div>
      )}

      {phase === "error" && (
        <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </p>
      )}

      {phase === "done" && result && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              {result.role_title}
              {result.company ? ` @ ${result.company}` : ""}
            </h3>
            <button
              onClick={() => {
                setPhase("idle");
                setResult(null);
              }}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100"
            >
              再定制一份
            </button>
          </div>
          <ResultView candidateId={candidateId} runId={result.run_id} summary={result} />
        </div>
      )}
    </div>
  );
}
