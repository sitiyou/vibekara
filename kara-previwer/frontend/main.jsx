import React, { useState, useEffect, useRef } from "react";
import { Camera, Layers, Maximize, Minimize, StepBack, StepForward } from "lucide-react";
import { createRoot } from "react-dom/client";
import { segmentPlayer } from "./segments";
import { createRenderer } from "./renderer";
import { Field } from "./fields";
import { Annotation } from "./annotations";
import "media-chrome/media-controller";
import "media-chrome/media-control-bar";
import "media-chrome/media-play-button";
import "media-chrome/media-time-range";
import "media-chrome/media-volume-range";
import "media-chrome/media-mute-button";
import { Library } from "./library";
import "./style.css";

async function api(path, body) {
  const r = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const result = await r.json();
  if (!r.ok) throw Error(result.error);
  return result;
}
function App() {
  const [state, setState] = useState(null),
    [proposal, setProposal] = useState(null),
    [values, setValues] = useState({});
  const [rangeDrafts, setRangeDrafts] = useState({});
  const [status, setStatus] = useState("正在加载"),
    [history, setHistory] = useState([]),
    [note, setNote] = useState("");
  const [frames, setFrames] = useState([]),
    [capture, setCapture] = useState(null),
    [compare, setCompare] = useState(null);
  const [ready, setReady] = useState(false),
    [panel, setPanel] = useState("设计"),
    [busy, setBusy] = useState(false);
  const canvas = useRef(),
    audio = useRef(),
    renderer = useRef(),
    presented = useRef(),
    clock = useRef(),
    fallback = useRef();
  const cached = useRef(new Map()),
    latest = useRef(0),
    receipt = useRef(),
    eventId = useRef(0),
    stateVersion = useRef(-1),
    acceptedToken = useRef(null);
  const segments = useRef(null), resume = useRef(false), segmentHooks = useRef(new Map());
  const [ranges, setRanges] = useState([]);
  const renderRequests = useRef({});
  const [connection, setConnection] = useState(0);
  const [direction, setDirection] = useState(0),
    [sideOpen, setSideOpen] = useState(true);
  async function requestPreview(start, current, prefetch = false) {
    const lane = prefetch ? "lookahead" : "current";
    while (current()) {
      const running = renderRequests.current[lane];
      if (running) {
        await running.catch(() => {});
        continue;
      }
      const request = start();
      renderRequests.current[lane] = request;
      try {
        return await request;
      } finally {
        delete renderRequests.current[lane];
      }
    }
    throw new DOMException("Preview selection changed", "AbortError");
  }
  function choose(revision, snapshot, index = 0) {
    const p = index
      ? { ...revision.directions[index - 1], version: revision.version }
      : revision;
    setDirection(index);
    setProposal(p);
    setValues(snapshot ?? p.values ?? {});
    setRangeDrafts({});
    setReady(false);
  }
  async function refresh() {
    const next = await api("state");
    if (next.cursor < eventId.current) return;
    setState(next);
    eventId.current = next.cursor;
    if (
      stateVersion.current !== next.version ||
      acceptedToken.current !== next.accepted
    ) {
      acceptedToken.current = next.accepted;
      stateVersion.current = next.version;
      if (next.version)
        choose(
          next.revisions[(next.saved?.version ?? next.version) - 1],
          next.saved?.values,
          next.saved?.direction || 0,
        );
    }
    setHistory(await api("history"));
  }
  useEffect(() => {
    let events,
      alive = true;
    const recover = async () => {
      try {
        await refresh();
        if (!alive) return;
        setConnection((n) => n + 1);
        if (!events) {
          events = new EventSource("events?after=" + eventId.current);
          events.onopen = () => refresh().catch((e) => setStatus(e.message));
          events.onmessage = (e) => {
            const event = JSON.parse(e.data);
            if (event.kind === "working") setStatus("Agent 正在修订");
            if (event.kind === "feedback") setStatus("意见已保存");
            refresh().catch((e) => setStatus(e.message));
          };
        }
      } catch (e) {
        if (alive) setStatus(e.message);
      }
    };
    recover();
    window.addEventListener("online", recover);
    return () => {
      alive = false;
      window.removeEventListener("online", recover);
      events?.close();
    };
  }, []);
  function draw(frame, force = false) {
    const view = presented.current;
    if (segments.current) {
      const {player, clip} = segments.current;
      const target = frame ?? Math.floor(audio.current.currentTime * clip.fps + .001);
      if (!player.select(target) || (clip.motion && (audio.current.seeking || audio.current.readyState < 2))) {
        setReady(false);
        return;
      }
      setReady(true);
    }
    if (!view) return;
    const c = view.clip;
    if (!segments.current && c.motion) {
      const decoded = !audio.current.seeking && audio.current.readyState >= 2;
      setReady(decoded);
      if (!decoded) return;
    }
    const i = Math.max(
      0,
      Math.min(
        Math.ceil(c.duration * c.fps) - 1,
        frame ?? Math.floor(audio.current.currentTime * c.fps + 0.001),
      ),
    );
    if (view.fallback) {
      const video = fallback.current;
      const offset = view.mediaOffset || 0;
      if (audio.current.paused || frame !== undefined) {
        video.pause();
        if (Math.abs(video.currentTime - (i / c.fps - offset)) > 0.001)
          video.currentTime = Math.max(0, i / c.fps - offset);
      } else {
        if (Math.abs(video.currentTime - (audio.current.currentTime - offset)) > 1 / c.fps)
          video.currentTime = Math.max(0, audio.current.currentTime - offset);
        if (video.paused) video.play().catch(() => {});
      }
    } else {
      if (!force && frame === undefined && view.frame === i) return;
      renderer.current.draw(c.start + i / c.fps);
    }
    view.frame = i;
    canvas.current.dataset.frame = i;
    const ms = Math.round((c.start + i / c.fps) * 1000);
    clock.current.textContent = Math.floor(ms / 60000) + ":" + ((ms % 60000) / 1000).toFixed(3).padStart(6, "0");
  }
  useEffect(() => {
    let raf;
    const tick = () => {
      if (!audio.current?.paused) draw();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  useEffect(() => {
    if (!proposal) return;
    const seq = ++latest.current;
    const changed = Object.entries(values).some(([key, value]) =>
      !(key in (proposal.palette || {})) && value !== proposal.values[key]);
    const clip = changed && proposal.clip.edit_segment_frames
      ? {...proposal.clip, segment_frames: proposal.clip.edit_segment_frames}
      : proposal.clip;
    const unavailable = Object.entries(proposal.fonts || {}).find(
      ([field, fonts]) => !fonts.includes(values[field]),
    );
    if (unavailable) {
      setReady(false);
      setStatus("字体不可用，请重新选择 " + values[unavailable[0]]);
      return;
    }
    if (clip.segment_frames) {
      const media = audio.current;
      const previous = presented.current;
      presented.current = null;
      setReady(false);
      setRanges([]);
      if (media.getAttribute("src") !== clip.audio) {
        const position = previous && previous.clip.audio !== clip.audio
          ? (previous.clip.start + previous.frame / previous.clip.fps - clip.start)
          : (clip.entry_frame || 0) / clip.fps;
        media.src = clip.audio;
        media.currentTime = Math.max(0, Math.min(position, clip.duration));
      }
      const player = segmentPlayer({proposal: {...proposal, clip}, values, direction, media, api, requestPreview, resume, hookCache: segmentHooks.current,
        canvas: canvas.current, fallback: fallback.current,
        renderer: () => (renderer.current ??= createRenderer(canvas.current)),
        present: view => { presented.current = view; setReady(true); },
        redraw: () => draw(undefined, true), status: setStatus,
        buffered: (a,b) => setRanges(old => [...old.filter(r => r[0] !== a), [a,b]]),
        active: () => latest.current === seq});
      segments.current = {player, clip};
      draw();
      return () => { player.stop(); segments.current = null; ++latest.current; };
    }
    const geometry = { ...values, ...proposal.palette };
    const key = JSON.stringify([proposal.version, direction, geometry]);
    setReady(false);
    const hit = cached.current.get(key);
    async function apply() {
      try {
        let hook = hit;
        if (
          !hook &&
          JSON.stringify(geometry) ===
            JSON.stringify({ ...proposal.values, ...proposal.palette })
        ) {
          hook = proposal.hook;
        }
        if (!hook) {
          ({ hook } = await requestPreview(
            () => api("render", {version: proposal.version, direction, values}),
            () => seq === latest.current,
          ));
        }
        cached.current.set(key, hook);
        if (seq !== latest.current) return;
        let native = false;
        try {
          renderer.current ??= createRenderer(canvas.current);
          const activate = await renderer.current.prepare(
            hook,
            clip.background,
            proposal.palette,
            values,
            clip.motion,
          );
          if (seq !== latest.current) return;
          activate();
        } catch (e) {
          setStatus("正在生成原生预渲染片段");
          native = (
            await api("native", {
              version: proposal.version,
              direction,
              values,
            })
          ).video;
          if (seq !== latest.current) return;
        }
        const previous = presented.current;
        if (audio.current.getAttribute("src") !== clip.audio) {
          const position = previous
            ? previous.clip.start + audio.current.currentTime - clip.start
            : (clip.entry_frame || 0) / clip.fps;
          const playing = !audio.current.paused;
          audio.current.src = clip.audio;
          audio.current.currentTime = Math.max(
            0,
            Math.min(position, clip.duration),
          );
          if (playing) audio.current.play().catch(() => {});
        }
        canvas.current.hidden = native;
        fallback.current.hidden = !native;
        if (native) {
          fallback.current.src = native;
          await new Promise((ok, fail) => {
            fallback.current.onloadeddata = ok;
            fallback.current.onerror = fail;
          });
          if (seq !== latest.current) return;
        }
        presented.current = {
          clip,
          hook,
          version: proposal.version,
          direction,
          values,
          frame: -1,
          fallback: native,
        };
        setReady(true);
        draw(undefined, true);
        setStatus(native ? "原生预渲染片段" : "实时预览");
        canvas.current.dataset.hook = hook;
        canvas.current.dataset.values = JSON.stringify(values);
        if (resume.current) {
          resume.current = false;
          audio.current.play().catch(() => {});
        }
      } catch (e) {
        if (seq === latest.current) setStatus(e.message);
      }
    }
    if (hit) {
      apply();
      return () => {
        latest.current++;
      };
    }
    const timer = setTimeout(apply, 35);
    return () => {
      clearTimeout(timer);
      latest.current++;
    };
  }, [proposal, values, connection]);
  function step(n) {
    const v = presented.current;
    if (!v) return;
    audio.current.pause();
    const i = Math.max(
      0,
      Math.min(Math.ceil(v.clip.duration * v.clip.fps) - 1, v.frame + n),
    );
    audio.current.currentTime = i / v.clip.fps;
    draw(i);
    return i;
  }
  async function grab() {
    const v = presented.current;
    if (!v || !ready) return;
    audio.current.pause();
    const target = v.frame / v.clip.fps;
    const media = audio.current;
    if (Math.abs(media.currentTime - target) > .00001) media.currentTime = target;
    if (v.clip.motion && media.seeking) {
      await new Promise(resolve => media.addEventListener("seeked", resolve, {once: true}));
    }
    if (presented.current !== v) return;
    draw(Math.round(target * v.clip.fps), true);
    if (v.fallback && fallback.current.seeking) {
      await new Promise((resolve) =>
        fallback.current.addEventListener("seeked", resolve, { once: true }),
      );
    }
    let pixels = canvas.current;
    if (v.fallback || v.clip.motion) {
      pixels = document.createElement("canvas");
      pixels.width = canvas.current.width;
      pixels.height = canvas.current.height;
      const capture = pixels.getContext("2d");
      capture.drawImage(v.fallback ? fallback.current : media, 0, 0, pixels.width, pixels.height);
      if (!v.fallback)
        capture.drawImage(canvas.current, 0, 0, pixels.width, pixels.height);
    }
    setCompare(null);
    setCapture({
      width: pixels.width,
      height: pixels.height,
      image: pixels.toDataURL(),
      values: v.values,
      hook: v.hook,
      version: v.version,
      direction: v.direction,
      clip: v.clip.id,
      fps: v.clip.fps,
      frame: v.frame,
      start: v.clip.start,
      time: v.clip.start + v.frame / v.clip.fps,
    });
  }
  async function submit(action) {
    const v = presented.current;
    if (!ready || busy) return;
    const data = {
      action,
      base: state.version,
      version: v.version,
      direction: v.direction,
      values,
      hook: v.hook,
      clip: v.clip.id,
      frame: v.frame,
      time: v.clip.start + v.frame / v.clip.fps,
      note,
      frames,
    };
    // A lost acknowledgement can arrive after the audio has advanced. Reuse
    // the original playback position and token when retrying that submission.
    const fingerprint = JSON.stringify({
      ...data,
      frame: undefined,
      time: undefined,
    });
    if (receipt.current?.fingerprint !== fingerprint)
      receipt.current = {
        fingerprint,
        payload: { ...data, token: crypto.randomUUID() },
      };
    setBusy(true);
    try {
      await api("submit", receipt.current.payload);
      receipt.current = null;
      setStatus(action === "accept" ? "已采用这版" : "意见已保存");
      setFrames([]);
      setNote("");
      await refresh();
    } catch (e) {
      setStatus(e.message);
    } finally {
      setBusy(false);
    }
  }
  function toggle() {
    if (!presented.current || capture) return;
    if (audio.current.paused)
      audio.current.play().catch((e) => setStatus(e.message));
    else audio.current.pause();
  }
  useEffect(() => {
    function key(e) {
      if (
        !ready ||
        capture ||
        e.defaultPrevented ||
        e.isComposing ||
        e.ctrlKey ||
        e.altKey ||
        e.metaKey ||
        e.target.closest(
          'input, textarea, select, button, summary, [contenteditable], [role="dialog"], media-control-bar',
        ) ||
        document.querySelector('[role="dialog"]:not([hidden])')
      )
        return;
      if (e.code === "Space") toggle();
      else if (e.key === "ArrowLeft" || e.key === "ArrowRight")
        step(e.key === "ArrowLeft" ? -1 : 1);
      else if (e.key.toLowerCase() === "s") grab();
      else return;
      e.preventDefault();
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  });
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    const sync = () => setFullscreen(document.fullscreenElement?.id === "review-player");
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);
  const clip = proposal?.clip;
  const Media = clip?.motion ? "video" : "audio";
  const revision = state?.revisions[proposal?.version - 1];
  const percentOf = proposal?.percent_of ?? {};
  const sizeFields = new Set(Object.values(percentOf));
  function field(f) {
    const reference = percentOf[f.name];
    return (
      <Field
        key={f.name}
        field={f}
        fonts={proposal.fonts?.[f.name]}
        sample={proposal.sample}
        value={values[f.name]}
        referenceSize={rangeDrafts[reference] ?? values[reference]}
        onDraft={sizeFields.has(f.name) ? (draft) => {
          setRangeDrafts((current) => ({ ...current, [f.name]: draft }));
        } : undefined}
        change={(value) =>
          setValues((current) => ({ ...current, [f.name]: value }))
        }
      />
    );
  }
  const focus = proposal?.focus;
  const groups = proposal?.groups || {};
  const grouped = new Set(Object.values(groups).flat());
  function fields(list) {
    return (
      <>
        {Object.entries(groups).map(([title, ids]) => {
          const members = list.filter((f) => ids.includes(f.name));
          return members.length ? (
            <fieldset key={title}>
              <legend>{title}</legend>
              {members.map(field)}
            </fieldset>
          ) : null;
        })}
        {list.filter((f) => !grouped.has(f.name)).map(field)}
      </>
    );
  }
  return (
    <main>
      <header>
        <span>Kara Previwer</span>
        <span>样式评审</span>
      </header>
      <h1>{state?.title || "打开评审"}</h1>
      <button
        className="panel-toggle"
        aria-expanded={sideOpen}
        onClick={() => setSideOpen(!sideOpen)}
      >
        设计与意见
      </button>
      <div className={"workspace " + (sideOpen ? "expanded" : "collapsed")}>
        <article id="review-player">
          <div
            className="screen"
            hidden={!!capture}
            onClick={toggle}
            onWheel={(e) => {
              if (!capture && audio.current?.paused && !e.ctrlKey && e.deltaY)
                step(Math.sign(e.deltaY));
            }}
          >
            <media-controller id="clock-controller" audio="" nohotkeys="">
              <Media
                playsInline
                ref={audio}
                slot="media"
                loop
                onPause={() => { fallback.current?.pause(); draw(); }}
                onSeeking={() => draw()}
                onLoadedData={() => draw(undefined, true)}
                onSeeked={() => draw(undefined, true)}
              />
            </media-controller>
            <canvas
              ref={canvas}
              width={clip?.width || 1280}
              height={clip?.height || 720}
            />
            <video hidden muted ref={fallback} />
            {compare && <img className="original" src={compare.annotated} />}
          </div>
          {capture && (
            <Annotation
              key={capture.time + "-" + capture.version}
              frame={capture}
              onAdd={(f) => {
                setFrames([...frames, f]);
                setCapture(null);
                setPanel("本轮意见");
              }}
              onClose={() => setCapture(null)}
            />
          )}
          <div className="transport">
            <media-control-bar mediacontroller="clock-controller">
              <media-play-button />
              <button type="button" aria-label="上一帧" title="上一帧（←）" disabled={!ready}
                onClick={() => { step(-1); if (capture) grab(); }}><StepBack /></button>
              <button type="button" aria-label="下一帧" title="下一帧（→）" disabled={!ready}
                onClick={() => { step(1); if (capture) grab(); }}><StepForward /></button>
              <media-time-range onKeyDown={e => {
                if (e.code !== "Space" || e.ctrlKey || e.altKey || e.metaKey || e.isComposing || capture) return;
                e.preventDefault();
                if (!e.repeat) toggle();
              }} />
              <span className="playback-clock" ref={clock} />
              <media-mute-button />
              <media-volume-range />
              <button type="button" aria-label="截帧提意见" title="截帧提意见（S）" disabled={!ready}
                onClick={grab}><Camera /></button>
              {compare && <button type="button" aria-label="查看当前版" title="查看当前版" onClick={() => setCompare(null)}><Layers /></button>}
              <button type="button" aria-label={fullscreen ? "退出全屏" : "全屏"} title={fullscreen ? "退出全屏" : "全屏"}
                onClick={e => fullscreen ? document.exitFullscreen() : e.currentTarget.closest("article").requestFullscreen()}>
                {fullscreen ? <Minimize /> : <Maximize />}
              </button>
            </media-control-bar>
          </div>
          {clip?.segment_frames && <div className="subtitle-buffer" aria-label="字幕已缓冲区间"><small>字幕缓冲</small><div>{ranges.map(([a,b]) =>
            <i key={a} title={`${(a/clip.fps).toFixed(1)}–${(b/clip.fps).toFixed(1)} s`} style={{left:100*a/(clip.duration*clip.fps)+"%",width:100*(b-a)/(clip.duration*clip.fps)+"%"}}/>)}</div></div>}
          <output role="status">
            {state?.accepted
              ? "已采用这版"
              : state?.working
                ? "Agent 正在修订"
                : status === "实时预览" && state?.saved
                  ? "意见已保存 · 实时预览"
                  : status}
          </output>
        </article>
        <aside>
          <nav>
            {["设计", "本轮意见", "收藏"].map((name) => (
              <button
                key={name}
                aria-pressed={panel === name}
                onClick={() => setPanel(name)}
              >
                {name}
                {name === "本轮意见" && frames.length
                  ? " · " + frames.length
                  : ""}
              </button>
            ))}
          </nav>
          {panel === "设计" ? (
            <>
              <label>
                方案版本{" "}
                <select
                  value={proposal?.version || ""}
                  onChange={(e) => choose(state.revisions[+e.target.value - 1])}
                >
                  {state?.revisions.map((p) => (
                    <option key={p.version} value={p.version}>
                      第 {p.version} 版
                    </option>
                  ))}
                </select>
              </label>
              {revision?.directions?.length > 0 && (
                <fieldset>
                  <legend>选择方向</legend>
                  {[revision, ...revision.directions].map((p, i) => (
                    <button
                      key={i}
                      aria-pressed={direction === i}
                      onClick={() => choose(revision, null, i)}
                    >
                      {p.title || p.template} · {p.summary}
                    </button>
                  ))}
                </fieldset>
              )}
              <p>{proposal?.summary}</p>
              {proposal?.not_inherited?.length > 0 && (
                <p>新模板未继承 {proposal.not_inherited.join("、")}</p>
              )}
              {proposal?.presets?.length > 0 && (
                <div className="buttons">
                  {proposal.presets.map((p) => (
                    <button
                      key={p.title}
                      onClick={() => {
                        setRangeDrafts({});
                        setValues({ ...proposal.values, ...p.values });
                      }}
                    >
                      {p.title}
                    </button>
                  ))}
                </div>
              )}
              {fields(
                (proposal?.parameters || []).filter(
                  (f) => !focus?.length || focus.includes(f.name),
                ),
              )}
              {focus?.length > 0 && (
                <details>
                  <summary>全部参数</summary>
                  {fields(
                    proposal.parameters.filter((f) => !focus.includes(f.name)),
                  )}
                </details>
              )}
            </>
          ) : panel === "收藏" ? (
            <Library
              api={api}
              ready={ready}
              accepted={!!state?.accepted}
              refresh={refresh}
              snapshot={() => ({
                version: proposal.version,
                base: state.version,
                direction,
                values,
                hook: presented.current?.hook,
                frame: presented.current?.frame,
              })}
            />
          ) : (
            <>
              {frames.map((f, i) => (
                <div className="thumb" key={i}>
                  <img src={f.annotated} />
                  <textarea
                    aria-label="编辑批注"
                    value={f.note}
                    onChange={(e) =>
                      setFrames(
                        frames.map((item, j) =>
                          i === j ? { ...item, note: e.target.value } : item,
                        ),
                      )
                    }
                  />
                  <button
                    onClick={() => setFrames(frames.filter((_, j) => i !== j))}
                  >
                    移除
                  </button>
                </div>
              ))}
              {history.map((h) => (
                <section key={h.id}>
                  <strong>
                    第 {h.version} 版 ·{" "}
                    {h.action === "accept" ? "已采用" : "已提交"}
                  </strong>
                  <p>{h.note}</p>
                  {h.frames?.map((f, i) => (
                    <button
                      key={i}
                      className="thumb"
                      onClick={() => {
                        audio.current.pause();
                        audio.current.currentTime = f.time - clip.start;
                        draw(Math.round((f.time - clip.start) * clip.fps));
                        setCapture(null);
                        setCompare(f);
                      }}
                    >
                      <img src={f.annotated} />
                      {f.time.toFixed(3)} s · {f.note}
                    </button>
                  ))}
                </section>
              ))}
            </>
          )}
          <textarea
            aria-label="修改意见"
            placeholder="描述你想调整的地方…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="buttons">
            <button
              disabled={!ready || busy || state?.accepted}
              onClick={() => submit("feedback")}
            >
              提交修改意见
            </button>
            <button
              className="primary"
              disabled={!ready || busy || state?.accepted}
              onClick={() => submit("accept")}
            >
              采用这版
            </button>
          </div>
        </aside>
      </div>
    </main>
  );
}
createRoot(document.querySelector("#root")).render(<App />);
