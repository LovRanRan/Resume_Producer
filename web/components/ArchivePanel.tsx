"use client";

import { useEffect, useState } from "react";
import { apiGetText, apiSend } from "@/lib/api";

export default function ArchivePanel({
  candidateId,
  onSaved,
}: {
  candidateId: string;
  onSaved: () => void;
}) {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    apiGetText(`/api/candidates/${candidateId}/master`)
      .then(setMarkdown)
      .catch((e) => setNotice({ ok: false, text: e.message }));
  }, [candidateId]);

  async function save() {
    if (markdown === null) return;
    setSaving(true);
    setNotice(null);
    try {
      const res = await apiSend<{ warnings: string[]; bullets: number }>(
        `/api/candidates/${candidateId}/master`,
        "PUT",
        { markdown }
      );
      setNotice({
        ok: true,
        text:
          `已保存并重新导入（${res.bullets} 条 bullet）` +
          (res.warnings.length ? `；警告：${res.warnings.join("；")}` : ""),
      });
      onSaved();
    } catch (e) {
      setNotice({ ok: false, text: `保存失败：${(e as Error).message}` });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-500">
        master 档案是唯一数据源：写得越全，AI 定制的选择空间越大。改完点保存即重新解析导入。
      </p>
      {markdown === null ? (
        <p className="text-sm text-zinc-400">加载中…</p>
      ) : (
        <textarea
          value={markdown}
          onChange={(e) => setMarkdown(e.target.value)}
          rows={28}
          spellCheck={false}
          className="w-full rounded-xl border border-zinc-300 bg-white p-4 font-mono text-[13px] leading-relaxed focus:border-indigo-500 focus:outline-none"
        />
      )}
      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving || markdown === null}
          className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? "保存中…" : "保存并重新导入"}
        </button>
        {notice && (
          <span className={`text-sm ${notice.ok ? "text-emerald-700" : "text-red-600"}`}>
            {notice.text}
          </span>
        )}
      </div>
    </div>
  );
}
