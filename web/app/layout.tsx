import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Resume Producer",
  description: "按 JD 定制简历生成器 — master 档案 → AI 筛选改写 → 单页 PDF",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
        <header className="border-b border-zinc-200 bg-white">
          <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-3">
            <a href="/" className="text-lg font-semibold tracking-tight">
              Resume<span className="text-indigo-600">Producer</span>
            </a>
            <span className="text-xs text-zinc-400">
              一份 master 档案 · 无限份定制简历
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
