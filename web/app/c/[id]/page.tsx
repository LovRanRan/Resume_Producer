"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ArchivePanel from "@/components/ArchivePanel";
import HistoryPanel from "@/components/HistoryPanel";
import TailorPanel from "@/components/TailorPanel";
import { apiGet } from "@/lib/api";

type Tab = "tailor" | "archive" | "history";

interface CandidateDetail {
  id: string;
  basic: { name: string };
  education: unknown[];
  experience: { bullets: unknown[] }[];
  projects: { bullets: unknown[] }[];
  skills: unknown[];
}

export default function Workspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [tab, setTab] = useState<Tab>("tailor");
  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    apiGet<CandidateDetail>(`/api/candidates/${id}`)
      .then(setCandidate)
      .catch((e) => setError(e.message));
  }, [id]);

  useEffect(refresh, [refresh]);

  if (error)
    return (
      <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error} — <Link href="/" className="underline">返回列表</Link>
      </p>
    );
  if (!candidate) return <p className="text-sm text-zinc-400">加载中…</p>;

  const bullets = [...candidate.experience, ...candidate.projects].reduce(
    (n, e) => n + e.bullets.length,
    0
  );

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-xs text-zinc-400">
            <Link href="/" className="hover:text-indigo-600">
              候选人
            </Link>{" "}
            / {candidate.id}
          </div>
          <h1 className="mt-1 text-2xl font-semibold">{candidate.basic.name}</h1>
        </div>
        <div className="text-sm text-zinc-500">
          项目 {candidate.projects.length} · 经历 {candidate.experience.length} · bullet{" "}
          {bullets}
        </div>
      </div>

      <nav className="flex gap-1 border-b border-zinc-200">
        {(
          [
            ["tailor", "定制简历"],
            ["archive", "master 档案"],
            ["history", "产出历史"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${
              tab === key
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-zinc-500 hover:text-zinc-800"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "tailor" && <TailorPanel candidateId={id} />}
      {tab === "archive" && <ArchivePanel candidateId={id} onSaved={refresh} />}
      {tab === "history" && <HistoryPanel candidateId={id} />}
    </div>
  );
}
