import React, { useEffect, useState } from "react";

export function Library({ api, snapshot, ready, accepted, refresh }) {
  const [prefs, setPrefs] = useState(null),
    [key, select] = useState("");
  const [name, setName] = useState(""),
    [description, describe] = useState("");
  const [message, report] = useState(""),
    [busy, setBusy] = useState(false);
  const [draft, edit] = useState("");
  function load(p) {
    setPrefs(p);
    edit(p.text);
    report(p.error || "");
  }
  useEffect(() => {
    api("preferences")
      .then(load)
      .catch((e) => report(e.message));
  }, []);
  async function act(action) {
    setBusy(true);
    try {
      if (action === "reuse") {
        await api("reuse", { ...snapshot(), key });
        await refresh();
      } else if (action === "preferences") {
        load(await api(action, { text: draft, digest: prefs.digest }));
      } else {
        const data = { action, digest: prefs.digest, key, name, description };
        if (["add", "update"].includes(action)) Object.assign(data, snapshot());
        const next = await api("collection", data);
        load(next);
        select(next.templates.find((i) => i.name === name)?.id || "");
      }
      report("已保存");
    } catch (e) {
      report(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <fieldset disabled={busy || !prefs}>
      <legend>我的模板</legend>
      <label>
        模板收藏
        <select
          value={key}
          onChange={(e) => {
            select(e.target.value);
            const entry = prefs.templates.find((i) => i.id === e.target.value);
            setName(entry?.name || "");
            describe(entry?.description || "");
          }}
        >
          <option value="">新收藏</option>
          {prefs?.templates.map((i) => (
            <option key={i.id} value={i.id}>
              {i.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        名称
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        说明
        <input value={description} onChange={(e) => describe(e.target.value)} />
      </label>
      <div className="buttons">
        <button disabled={!ready || !name} onClick={() => act("add")}>
          另存当前模板
        </button>
        {key && (
          <>
            <button disabled={accepted || !ready} onClick={() => act("reuse")}>
              在本曲使用
            </button>
            <button disabled={!ready || !name} onClick={() => act("update")}>
              用当前选值更新
            </button>
            <button onClick={() => act("rename")}>保存名称和说明</button>
            <button onClick={() => act("remove")}>移出收藏</button>
          </>
        )}
      </div>
      <details>
        <summary>编辑个人偏好</summary>
        <textarea
          aria-label="个人偏好 Markdown"
          value={draft}
          onChange={(e) => edit(e.target.value)}
        />
        <small>{new TextEncoder().encode(draft).length} / 4096 字节</small>
        <button onClick={() => act("preferences")}>保存偏好</button>
        {prefs?.last_valid && (
          <button onClick={() => edit(prefs.last_valid)}>
            取回上次有效内容
          </button>
        )}
        <button
          onClick={async () => {
            try {
              const latest = await api("preferences");
              setPrefs(latest);
              report("已读取当前文件，请合并后保存");
            } catch (e) {
              report(e.message);
            }
          }}
        >
          读取最新内容以合并
        </button>
        {prefs && prefs.text !== draft && <pre>{prefs.text}</pre>}
      </details>
      <output>{message}</output>
    </fieldset>
  );
}
