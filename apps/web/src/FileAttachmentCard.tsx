import { Capacitor, registerPlugin } from "@capacitor/core";
import { useState } from "react";
import { Download, FileText } from "lucide-react";
import { workspaceApi } from "./api";

const nativeFile = registerPlugin<{ share(input: { name: string; base64: string }): Promise<{ completed: boolean }> }>("AdexFile");

export function FileAttachmentCard({ data }: { data: Record<string, unknown> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const name = String(data.name || "附件");
  async function download() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const blob = await workspaceApi.blob(String(data.id));
      const file = new File([blob], name, { type: String(data.mime_type || blob.type) });
      if (Capacitor.isNativePlatform()) {
        const base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
          reader.onerror = () => reject(new Error("ATTACHMENT_READ_FAILED"));
          reader.readAsDataURL(blob);
        });
        await nativeFile.share({ name, base64 });
      } else if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: name });
      } else {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = name;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) setError("附件暂时无法打开，请重试。");
    } finally {
      setBusy(false);
    }
  }
  return <section className="file-return-card">
    <FileText size={24} aria-hidden="true" />
    <div><strong>{name}</strong><small>{Math.ceil(Number(data.size_bytes || 0) / 1024)} KB · 私人附件</small></div>
    <button className="icon-button" disabled={busy} aria-label={busy ? "正在读取附件" : "打开或保存附件"} onClick={() => void download()}><Download size={20} /></button>
    {error && <p role="alert">{error}</p>}
  </section>;
}
