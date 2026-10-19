import { useEffect, useState, useSyncExternalStore } from "react";
import { ArrowLeft, FileText, Download, Search } from "lucide-react";
import {
  request,
  workspaceApi,
  type Artifact,
  type ArtifactVersion,
  type StoredFile,
} from "./api";
import { createReadResource } from "./readResource";
import { usePageScroll } from "./usePageScroll";
import { Markdown } from "./Markdown";
const library = createReadResource(async (signal) => {
  const [files, artifacts] = await Promise.all([
    request<{ items: StoredFile[] }>("/files", "GET", undefined, undefined, {
      signal,
    }),
    request<{ items: Artifact[] }>("/artifacts", "GET", undefined, undefined, {
      signal,
    }),
  ]);
  return { files: files.items, artifacts: artifacts.items };
});
window.addEventListener("adex:session-changed", () => library.reset());
const kinds: Record<string, string> = {
  REPORT: "研究报告",
  RESEARCH: "研究报告",
  TRAVEL: "旅行攻略",
  IMAGE: "图片",
  AUDIO: "音乐",
  VIDEO: "视频",
  DIAGRAM: "图表",
  GAME: "互动作品",
};
export function MaterialLibrary() {
  const scroll = usePageScroll<HTMLDivElement>("materials");
  const snap = useSyncExternalStore(library.subscribe, library.getSnapshot);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<{
    artifact: Artifact;
    version?: ArtifactVersion;
  } | null>(null);
  const [error, setError] = useState("");
  const [opening, setOpening] = useState("");
  useEffect(() => {
    void library.load().catch(() => {});
  }, []);
  async function open(artifact: Artifact) {
    setOpening(artifact.id);
    setError("");
    try {
      const history = await workspaceApi.versions(artifact.id);
      setSelected({ artifact, version: history.items[0] });
    } catch {
      setError("暂时无法读取，请重试。");
    } finally {
      setOpening("");
    }
  }
  async function download(file: StoredFile) {
    try {
      const blob = await workspaceApi.blob(file.id),
        url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setError("下载未完成，请重试。");
    }
  }
  const matches = (text: string) =>
    text.toLocaleLowerCase().includes(query.toLocaleLowerCase());
  return (
    <div className="content-page material-library" ref={scroll}>
      {error && (
        <p role="alert" className="experience-inline-error">
          {error}
        </p>
      )}
      {selected ? (
        <>
          <header className="material-detail-heading">
            <button
              className="experience-icon"
              aria-label="返回资料列表"
              onClick={() => setSelected(null)}
            >
              <ArrowLeft size={20} />
            </button>
            <h2>{selected.artifact.title}</h2>
          </header>
          {selected.version?.source.content ? (
            <Markdown content={selected.version.source.content} />
          ) : (
            <p className="experience-empty">
              此资料没有文本正文，原文件可从文件列表下载。
            </p>
          )}
          {selected.version?.file_id &&
            snap.data?.files
              .filter((f) => f.id === selected.version?.file_id)
              .map((file) => (
                <button
                  key={file.id}
                  className="text-button"
                  onClick={() => void download(file)}
                >
                  <Download size={16} />
                  下载 {file.name}
                </button>
              ))}
        </>
      ) : (
        <>
          <label className="matrix-search">
            <Search size={17} />
            <input
              aria-label="搜索报告与文件"
              placeholder="搜索报告与文件"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          {snap.loading && !snap.data && <p role="status">正在读取资料…</p>}
          {!!snap.error && (
            <p role="alert">
              读取失败。
              <button onClick={() => void library.load(true).catch(() => {})}>
                重试
              </button>
            </p>
          )}
          <h3 className="task-day-heading">报告与生成内容</h3>
          {snap.data?.artifacts
            .filter((a) => matches(a.title))
            .map((a) => (
              <button
                className="material-row"
                key={a.id}
                disabled={!!opening}
                onClick={() => void open(a)}
              >
                <FileText size={19} />
                <span>
                  <strong>{a.title}</strong>
                  <small>
                    {opening === a.id
                      ? "正在读取…"
                      : `${kinds[a.kind] ?? "资料"} · 第 ${a.revision} 版`}
                  </small>
                </span>
              </button>
            ))}
          {!snap.data?.artifacts.some((a) => matches(a.title)) && snap.data && (
            <p className="experience-empty">
              聊天中生成的研究报告和内容会保存在这里。
            </p>
          )}
          <h3 className="task-day-heading">私有文件</h3>
          {snap.data?.files
            .filter((f) => matches(f.name))
            .map((f) => (
              <button
                className="material-row"
                key={f.id}
                onClick={() => void download(f)}
              >
                <FileText size={19} />
                <span>
                  <strong>{f.name}</strong>
                  <small>{(f.size_bytes / 1024).toFixed(0)} KB</small>
                </span>
                <Download size={17} />
              </button>
            ))}
        </>
      )}
    </div>
  );
}
