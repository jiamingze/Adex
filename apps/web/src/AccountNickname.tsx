import { useEffect, useState, useSyncExternalStore } from "react";
import { accountProfile, saveNickname } from "./accountProfile";
import { Button } from "@adex/ui-web";
export function AccountNickname() {
  const snapshot = useSyncExternalStore(
    accountProfile.subscribe,
    accountProfile.getSnapshot,
  );
  const [nickname, setNickname] = useState(snapshot.data?.nickname ?? "");
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  useEffect(() => {
    void accountProfile.load().catch(() => {});
  }, []);
  useEffect(() => {
    if (!dirty) setNickname(snapshot.data?.nickname ?? "");
  }, [snapshot.data?.nickname, dirty]);
  const invalid =
    Array.from(nickname.trim()).length > 40 ||
    /[\u0000-\u001f\u007f-\u009f]/.test(nickname);
  return (
    <form
      className="account-nickname"
      onSubmit={async (event) => {
        event.preventDefault();
        if (busy || invalid || !snapshot.data) return;
        setBusy(true);
        setNotice("");
        try {
          const saved = await saveNickname(nickname);
          setNickname(saved.nickname);
          setDirty(false);
          setNotice(saved.nickname ? "昵称已保存" : "已恢复显示账号名");
        } catch {
          setNotice("未能保存昵称，请检查连接后重试。");
        } finally {
          setBusy(false);
        }
      }}
    >
      <label htmlFor="account-nickname">昵称</label>
      <p>用于首页问候与头像，登录仍使用账号。留空可恢复账号名。</p>
      <div className="nickname-controls">
        <input
          id="account-nickname"
          autoComplete="nickname"
          placeholder="希望 Adex 怎么称呼你？"
          value={nickname}
          disabled={busy || !snapshot.data}
          onChange={(event) => {
            setNickname(event.target.value);
            setDirty(true);
            setNotice("");
          }}
        />
        <Button
          type="submit"
          disabled={busy || !dirty || invalid || !snapshot.data}
        >
          {busy ? "保存中…" : "保存昵称"}
        </Button>
      </div>
      {invalid && (
        <small role="alert">昵称最多 40 个字符，请勿包含换行或控制字符。</small>
      )}
      {!!snapshot.error && (
        <p role="status">
          暂时无法读取昵称。
          <button
            type="button"
            className="text-button"
            onClick={() => void accountProfile.load(true).catch(() => {})}
          >
            重试
          </button>
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
    </form>
  );
}
