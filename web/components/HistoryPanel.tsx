"use client";

import { useEffect, useState } from "react";
import ResultView from "./ResultView";
import { apiGet, type RunListItem } from "@/lib/api";

export default function HistoryPanel({ candidateId }: { candidateId: string }) {
  const [runs, setRuns] = useState<RunListItem[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<RunListItem[]>(`/api/candidates/${candidateId}/outputs`)
      .then((r) => {
        setRuns(r);
        if (r.length > 0) setSelected(r[0].run_id);
      })
      .catch((e) => setError(e.message));
  }, [candidateId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (runs === null) return <p className="text-sm text-zinc-400">加载中…</p>;
  if (runs.length === 0)
    return (
      <p className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-500">
        还没有产出记录。去「定制」页跑第一份。
      </p>
    );

  return (
    <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
      <div className="space-y-2">
        {runs.map((r) => {
          const ts = r.run_id.slice(0, 15); // YYYYMMDD-HHMMSS
          const date = `${ts.slice(4, 6)}/${ts.slice(6, 8)} ${ts.slice(9, 11)}:${ts.slice(11, 13)}`;
          return (
            <button
              key={r.run_id}
              onClick={() => setSelected(r.run_id)}
              className={`w-full rounded-lg border px-3 py-2.5 text-left text-sm transition ${
                selected === r.run_id
                  ? "border-indigo-400 bg-indigo-50"
                  : "border-zinc-200 bg-white hover:border-zinc-300"
              }`}
            >
              <div className="font-medium text-zinc-800">
                {r.role_title ?? r.run_id}
              </div>
              <div className="mt-0.5 text-xs text-zinc-400">
                {r.company ? `${r.company} · ` : ""}
                {date}
              </div>
            </button>
          );
        })}
      </div>
      <div>{selected && <ResultView candidateId={candidateId} runId={selected} />}</div>
    </div>
  );
}
