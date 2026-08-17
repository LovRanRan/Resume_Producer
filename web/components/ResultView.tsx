"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiGetText, fileUrl, type RunSummary } from "@/lib/api";

export default function ResultView({
  candidateId,
  runId,
  summary,
}: {
  candidateId: string;
  runId: string;
  summary?: RunSummary;
}) {
  const [report, setReport] = useState<string | null>(null);
  const [tab, setTab] = useState<"pdf" | "report">("pdf");
  const base = `/api/candidates/${candidateId}/outputs/${runId}`;

  useEffect(() => {
    setReport(null);
    apiGetText(`${base}/report.md`)
      .then(setReport)
      .catch(() => setReport("（报告加载失败）"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidateId, runId]);

  return (
    <div className="space-y-4">
      {summary && (
        <div className="flex flex-wrap gap-2 text-xs">
          <Chip>{summary.pages} 页</Chip>
          <Chip>项目 {summary.projects}</Chip>
          <Chip>经历 {summary.experience}</Chip>
          <Chip>bullet {summary.bullets}</Chip>
          <Chip>
            关键词 {summary.keywords_covered}/{summary.keywords_total}
          </Chip>
          {summary.trimmed > 0 && <Chip>裁剪 {summary.trimmed}</Chip>}
          {summary.fallbacks > 0 && <Chip warn>回退原文 {summary.fallbacks}</Chip>}
          <Chip>${summary.cost_usd.toFixed(3)}</Chip>
        </div>
      )}

      <div className="flex items-center gap-2">
        <TabBtn active={tab === "pdf"} onClick={() => setTab("pdf")}>
          简历 PDF
        </TabBtn>
        <TabBtn active={tab === "report"} onClick={() => setTab("report")}>
          定制报告
        </TabBtn>
        <span className="flex-1" />
        <a
          href={fileUrl(`${base}/resume.pdf`)}
          target="_blank"
          className="text-xs text-indigo-600 hover:underline"
        >
          下载 PDF
        </a>
        <a
          href={fileUrl(`${base}/resume.tex`)}
          target="_blank"
          className="text-xs text-indigo-600 hover:underline"
        >
          .tex
        </a>
      </div>

      {tab === "pdf" ? (
        <iframe
          src={fileUrl(`${base}/resume.pdf`)}
          className="h-[75vh] w-full rounded-xl border border-zinc-200 bg-white"
          title="resume pdf"
        />
      ) : (
        <div className="prose prose-sm prose-zinc max-w-none rounded-xl border border-zinc-200 bg-white p-6 [&_blockquote]:border-indigo-200 [&_blockquote]:text-zinc-600 [&_code]:rounded [&_code]:bg-zinc-100 [&_code]:px-1 [&_code]:font-mono [&_code]:text-[0.85em] [&_h2]:mt-6 [&_h2]:border-b [&_h2]:border-zinc-100 [&_h2]:pb-1 [&_h3]:mt-4">
          {report === null ? (
            <p className="text-zinc-400">报告加载中…</p>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
          )}
        </div>
      )}
    </div>
  );
}

function Chip({ children, warn = false }: { children: React.ReactNode; warn?: boolean }) {
  return (
    <span
      className={`rounded-full px-2.5 py-1 font-medium ${
        warn ? "bg-amber-100 text-amber-800" : "bg-indigo-50 text-indigo-700"
      }`}
    >
      {children}
    </span>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
        active ? "bg-zinc-900 text-white" : "bg-white text-zinc-600 hover:bg-zinc-100"
      }`}
    >
      {children}
    </button>
  );
}
