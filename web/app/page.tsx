"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  apiGet,
  apiSend,
  getToken,
  setToken,
  type CandidateSummary,
} from "@/lib/api";

export default function Home() {
  const [candidates, setCandidates] = useState<CandidateSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [markdown, setMarkdown] = useState("");
  const [importing, setImporting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [token, setTokenState] = useState("");

  const refresh = useCallback(() => {
    setError(null);
    apiGet<CandidateSummary[]>("/api/candidates")
      .then(setCandidates)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    setTokenState(getToken());
    refresh();
  }, [refresh]);

  async function doImport() {
    setImporting(true);
    setNotice(null);
    try {
      const res = await apiSend<{ id: string; warnings: string[] }>(
        "/api/candidates",
        "POST",
        { markdown }
      );
      setNotice(
        `已导入 ${res.id}` +
          (res.warnings.length ? `（${res.warnings.length} 条警告）` : "")
      );
      setMarkdown("");
      setShowImport(false);
      refresh();
    } catch (e) {
      setNotice(`导入失败：${(e as Error).message}`);
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">候选人档案</h1>
        <button
          onClick={() => setShowImport((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          导入 master 档案
        </button>
      </div>

      {showImport && (
        <div className="space-y-3 rounded-xl border border-zinc-200 bg-white p-4">
          <p className="text-sm text-zinc-500">
            粘贴 master markdown 档案（格式见仓库 docs/master-format.md）
          </p>
          <textarea
            value={markdown}
            onChange={(e) => setMarkdown(e.target.value)}
            rows={12}
            placeholder="## Basic Info&#10;Name: …"
            className="w-full rounded-lg border border-zinc-300 p-3 font-mono text-sm focus:border-indigo-500 focus:outline-none"
          />
          <button
            onClick={doImport}
            disabled={importing || !markdown.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {importing ? "解析中…" : "解析并导入"}
          </button>
        </div>
      )}

      {notice && (
        <p className="rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-800">{notice}</p>
      )}

      {error ? (
        <div className="space-y-3 rounded-xl border border-red-200 bg-red-50 p-5 text-sm">
          <p className="font-medium text-red-700">无法连接后端：{error}</p>
          <p className="text-red-600">
            请确认已启动 <code className="rounded bg-red-100 px-1">uv run resume api</code>
            ；若后端设置了 RESUME_API_TOKEN，在下方填入：
          </p>
          <div className="flex gap-2">
            <input
              value={token}
              onChange={(e) => setTokenState(e.target.value)}
              placeholder="API token（可选）"
              className="rounded-lg border border-red-200 bg-white px-3 py-1.5"
            />
            <button
              onClick={() => {
                setToken(token);
                refresh();
              }}
              className="rounded-lg bg-red-600 px-3 py-1.5 text-white"
            >
              保存并重试
            </button>
          </div>
        </div>
      ) : candidates === null ? (
        <p className="text-sm text-zinc-400">加载中…</p>
      ) : candidates.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-500">
          还没有档案。点右上角「导入 master 档案」开始。
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {candidates.map((c) => (
            <Link
              key={c.id}
              href={`/c/${c.id}`}
              className="group rounded-xl border border-zinc-200 bg-white p-5 transition hover:border-indigo-300 hover:shadow-sm"
            >
              <div className="text-lg font-semibold group-hover:text-indigo-600">
                {c.name}
              </div>
              <div className="mt-1 text-xs text-zinc-400">{c.id}</div>
              <div className="mt-3 flex gap-4 text-sm text-zinc-600">
                <span>项目 {c.projects}</span>
                <span>经历 {c.experience}</span>
                <span>bullet {c.bullets}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
