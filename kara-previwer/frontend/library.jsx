import React, { useEffect, useState } from "react";
import { ChevronRight } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./cult/base-select";

export function Library({ api, snapshot, ready, canSave, accepted, refresh }) {
  const [prefs, setPrefs] = useState(null);
  const [key, select] = useState("");
  const [name, setName] = useState("");
  const [description, describe] = useState("");
  const [message, report] = useState("");
  const [busy, setBusy] = useState(false);
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
    <fieldset className="library-form" disabled={busy || !prefs}>
      <div className="library-field">
        <span>已收藏模板</span>
        <Select
          value={key || "__new__"}
          items={[
            { value: "__new__", label: "新收藏" },
            ...(prefs?.templates ?? []).map((i) => ({
              value: i.id,
              label: i.name,
            })),
          ]}
          onValueChange={(nextVal) => {
            const nextKey = nextVal === "__new__" ? "" : nextVal;
            select(nextKey);
            const entry = prefs?.templates.find((i) => i.id === nextKey);
            setName(entry?.name || "");
            describe(entry?.description || "");
          }}
        >
          <SelectTrigger aria-label="已收藏模板">
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start">
            <SelectItem value="__new__">新收藏</SelectItem>
            {prefs?.templates.map((i) => (
              <SelectItem key={i.id} value={i.id}>
                {i.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <label className="library-field">
        <span>名称</span>
        <input
          className="studio-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="给这套样式起个名字…"
        />
      </label>

      <label className="library-field">
        <span>说明</span>
        <input
          className="studio-input"
          value={description}
          onChange={(e) => describe(e.target.value)}
          placeholder="简短记录适用场景或风格…"
        />
      </label>

      <div className="library-actions">
        {canSave && (
          <button
            type="button"
            className="btn btn-sm"
            disabled={!name}
            onClick={() => act("add")}
          >
            另存当前模板
          </button>
        )}
        {key && (
          <>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={accepted || !ready}
              onClick={() => act("reuse")}
            >
              在本曲使用
            </button>
            {canSave && (
              <button
                type="button"
                className="btn btn-sm"
                disabled={!name}
                onClick={() => act("update")}
              >
                用当前选值更新
              </button>
            )}
            <button type="button" className="btn btn-sm" onClick={() => act("rename")}>
              保存名称和说明
            </button>
            <button
              type="button"
              className="btn btn-sm btn-danger-ghost"
              onClick={() => act("remove")}
            >
              移出收藏
            </button>
          </>
        )}
      </div>

      <details className="studio-details">
        <summary>
          <ChevronRight />
          编辑个人偏好（Markdown）
        </summary>
        <div className="studio-details-body">
          <textarea
            className="studio-textarea"
            aria-label="个人偏好 Markdown"
            value={draft}
            onChange={(e) => edit(e.target.value)}
          />
          <div className="library-prefs-meta">
            <span>{new TextEncoder().encode(draft).length} / 4096 字节</span>
            <div className="library-actions">
              {prefs?.last_valid && (
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  onClick={() => edit(prefs.last_valid)}
                >
                  取回上次有效
                </button>
              )}
              <button
                type="button"
                className="btn btn-sm"
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
                读取最新内容
              </button>
              <button
                type="button"
                className="btn btn-sm btn-primary"
                onClick={() => act("preferences")}
              >
                保存偏好
              </button>
            </div>
          </div>
          {prefs && prefs.text !== draft && <pre className="library-diff">{prefs.text}</pre>}
        </div>
      </details>

      {message && (
        <output style={{ fontSize: "var(--text-xs)", color: "var(--accent)" }}>
          {message}
        </output>
      )}
    </fieldset>
  );
}
