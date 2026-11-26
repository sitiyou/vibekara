import React, { useState, useEffect, useRef } from "react";
import {
  Bookmark,
  Camera,
  Check,
  ChevronRight,
  Layers,
  Layers3,
  Maximize,
  MessageSquare,
  Minimize,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  RotateCcw,
  SlidersHorizontal,
  StepBack,
  StepForward,
  Trash2,
  Type,
  Undo2,
  X,
} from "lucide-react";
import { createRoot } from "react-dom/client";
import { segmentPlayer } from "./segments";
import {
  createRenderer,
  materialValues,
  nativeFrame,
  sameValues,
} from "./renderer";
import { Field } from "./fields";
import { Annotation } from "./annotations";
import "media-chrome/media-controller";
import "media-chrome/media-control-bar";
import "media-chrome/media-play-button";
import "media-chrome/media-time-range";
import "media-chrome/media-volume-range";
import "media-chrome/media-mute-button";
import { Library } from "./library";
import { PropertyEditor } from "./composition-editor";
import {
  EffectsPanel,
  EffectsRack,
  trackEffectItems,
} from "./effect-editor";
import { CandidateCards } from "./preview-cards";
import {
  componentValue,
  compositionKey,
  makeNode,
  structureKey,
} from "./composition";
import { title } from "./composition-fields";
import { occupants, placeEffect } from "./effect-placement";
import { useWorkspaceLayout } from "./workspace-layout";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./cult/base-select";
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
  const [state, setState] = useState(null);
  const [proposal, setProposal] = useState(null);
  const [values, setValues] = useState({});
  const [rangeDrafts, setRangeDrafts] = useState({});
  const [composition, setComposition] = useState(undefined);
  const [saveStatus, setSaveStatus] = useState("");
  const [undoCount, setUndoCount] = useState(0);
  const [workspaceMode, setWorkspaceMode] = useState(null);
  const [editTab, setEditTab] = useState("style");
  const [panelOpen, setPanelOpen] = useState(true);
  const [libraryOpen, setLibraryOpen] = useState(false);

  // Composition tracks & effects coordination (shared between left rack & right panel)
  const [tracks, setTracks] = useState(null);
  const [tracksError, setTracksError] = useState("");
  const [effectTrack, setEffectTrack] = useState("");
  const [selectedEffectId, setSelectedEffectId] = useState(null);
  const [trialNode, setTrialNode] = useState(null);
  const [trial, setTrial] = useState(null);

  const layout = useWorkspaceLayout();
  const [status, setStatus] = useState("正在加载");
  const [history, setHistory] = useState([]);
  const [note, setNote] = useState("");
  const [frames, setFrames] = useState([]);
  const [capture, setCapture] = useState(null);
  const [compare, setCompare] = useState(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);

  const canvas = useRef();
  const audio = useRef();
  const renderer = useRef();
  const presented = useRef();
  const clock = useRef();
  const fallback = useRef();

  const cached = useRef(new Map());
  const latest = useRef(0);
  const receipt = useRef();
  const eventId = useRef(0);
  const stateVersion = useRef(-1);
  const acceptedToken = useRef(null);
  const segments = useRef(null);
  const resume = useRef(false);
  const segmentHooks = useRef(new Map());
  const renderRequests = useRef({});
  const [connection, setConnection] = useState(0);
  const [direction, setDirection] = useState(0);

  const current = useRef({ values, composition });
  current.current = { values, composition };
  const previewComposition = trial?.graph ?? composition;
  const preview = useRef({ values, composition: previewComposition });
  preview.current = { values, composition: previewComposition };

  const drafts = useRef(new Map());
  const gestures = useRef(null);
  const undoStack = useRef(new Map());
  const activeDraft = useRef(null);
  const [nativeActive, setNativeActive] = useState(false);

  const materialDefaults = proposal
    ? materialValues(proposal, proposal.values)
    : {};
  const geometryKey = JSON.stringify([
    proposal?.version,
    direction,
    { ...values, ...materialDefaults },
    structureKey(previewComposition),
  ]);
  const renderKey = nativeActive
    ? JSON.stringify([geometryKey, values, previewComposition])
    : geometryKey;

  async function requestPreview(start, isCurrent, prefetch = false) {
    const lane = prefetch ? "lookahead" : "current";
    while (isCurrent()) {
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

  function saveDraft(snapshot) {
    if (!proposal?.composition || state?.accepted) return;
    const version = proposal.version;
    const key = `${version}:${direction}`;
    const record = drafts.current.get(key) ?? { revision: 0 };
    record.snapshot = snapshot;
    drafts.current.set(key, record);
    setSaveStatus("正在保存…");
    const pending = (record.pending ?? Promise.resolve()).then(async () => {
      try {
        const result = await api("draft", {
          version,
          direction,
          revision: record.revision,
          ...snapshot,
        });
        record.revision = result.revision;
        if (record.snapshot === snapshot && activeDraft.current === key) {
          setSaveStatus("已保存");
        }
      } catch (error) {
        if (record.snapshot === snapshot && activeDraft.current === key) {
          setSaveStatus("未保存 · " + error.message);
        }
      }
    });
    record.pending = pending;
    pending.finally(() => {
      if (record.pending === pending) record.pending = null;
    });
  }

  function remember(snapshot) {
    const stack = undoStack.current.get(activeDraft.current) ?? [];
    stack.push(snapshot);
    if (stack.length > 50) stack.shift();
    undoStack.current.set(activeDraft.current, stack);
    setUndoCount(stack.length);
  }

  function editComposition(next, mode = "commit") {
    if (state?.accepted) return;
    const before = current.current;
    if (mode === "live") gestures.current ??= before;
    const origin = gestures.current ?? before;
    const after = { ...before, composition: next };
    current.current = after;
    setComposition(next);
    if (mode === "live") return;
    gestures.current = null;
    if (compositionKey(origin.composition) === compositionKey(next)) return;
    remember(origin);
    saveDraft(after);
  }

  function finishTrial() {
    setTrial(null);
    setTrialNode(null);
    setSelectedEffectId((id) => (id === "__trial__" ? null : id));
  }

  function resetComposition() {
    if (state?.accepted || !proposal) return;
    finishTrial();
    remember(gestures.current ?? current.current);
    gestures.current = null;
    const next = {
      values: proposal.values,
      composition: proposal.composition,
    };
    current.current = next;
    setValues(next.values);
    setComposition(next.composition);
    setSelectedEffectId(null);
    saveDraft(next);
  }

  function undo() {
    const stack = undoStack.current.get(activeDraft.current);
    if (!stack?.length || state?.accepted) return;
    finishTrial();
    const next = stack.pop();
    gestures.current = null;
    current.current = next;
    setUndoCount(stack.length);
    setValues(next.values);
    setComposition(next.composition);
    saveDraft(next);
  }

  function changeValue(name, value, commit = true) {
    const next = {
      ...current.current,
      values: { ...current.current.values, [name]: value },
    };
    current.current = next;
    setValues(next.values);
    if (commit && proposal?.composition) saveDraft(next);
  }

  function choose(revision, snapshot, index = 0, savedDrafts = state?.drafts) {
    const p = index
      ? { ...revision.directions[index - 1], version: revision.version }
      : revision;
    const key = `${p.version}:${index}`;
    activeDraft.current = key;
    sessionStorage.setItem(location.pathname + ":direction", key);
    let draft = drafts.current.get(key);
    const saved = savedDrafts?.[key];
    if (
      saved &&
      (!draft || (!draft.pending && saved.revision > draft.revision))
    ) {
      const { revision: rev, ...snap } = saved;
      draft = { revision: rev, snapshot: snap };
      drafts.current.set(key, draft);
    }
    const selected = snapshot ?? draft?.snapshot ?? p;
    setTrial(null);
    setTrialNode(null);
    setSelectedEffectId(null);
    setCompare(null);
    setDirection(index);
    setProposal(p);
    setValues(selected.values ?? {});
    setComposition(selected.composition ?? p.composition);
    setRangeDrafts({});
    gestures.current = null;
    setUndoCount(undoStack.current.get(key)?.length ?? 0);
    setSaveStatus(draft ? "已恢复草稿" : "");
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
      const first = stateVersion.current < 0;
      acceptedToken.current = next.accepted;
      stateVersion.current = next.version;
      if (next.version) {
        const [priorVersion, priorDirection] = (
          sessionStorage.getItem(location.pathname + ":direction") ?? ""
        )
          .split(":")
          .map(Number);
        const submitted = next.saved;
        const version = next.accepted
          ? submitted?.version ?? next.version
          : first && next.revisions[priorVersion - 1]
            ? priorVersion
            : next.version;
        const revision = next.revisions[version - 1];
        const priorIndex =
          first &&
          priorVersion === version &&
          priorDirection <= (revision.directions?.length ?? 0)
            ? priorDirection
            : 0;
        const index = next.accepted ? submitted?.direction ?? 0 : priorIndex;
        const saved =
          submitted?.version === version && submitted?.direction === index
            ? submitted
            : null;
        choose(
          revision,
          next.accepted
            ? submitted
            : next.drafts?.[`${version}:${index}`]
              ? null
              : saved,
          index,
          next.drafts,
        );
      }
    }
    setHistory(await api("history"));
  }

  useEffect(() => {
    let events;
    let alive = true;
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
            if (event.kind === "working") setStatus("正在修订");
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

  // Load composition tracks once per version/direction
  useEffect(() => {
    if (!proposal?.composition) {
      setTracks(null);
      setTracksError("");
      return;
    }
    let alive = true;
    setTracks(null);
    setTracksError("");
    api(
      `composition-details?version=${proposal.version}&direction=${direction}`,
    )
      .then((result) => {
        if (!alive) return;
        setTracks(result.tracks);
        const firstTrack = Object.keys(result.tracks)[0] ?? "";
        setEffectTrack((prev) => (result.tracks[prev] ? prev : firstTrack));
      })
      .catch(() => {
        if (alive) setTracksError("无法读取字幕声部");
      });
    return () => {
      alive = false;
    };
  }, [proposal?.version, proposal?.composition, direction]);

  function draw(frame, force = false) {
    const view = presented.current;
    if (segments.current) {
      const { player, clip } = segments.current;
      const target =
        frame ?? Math.floor(audio.current.currentTime * clip.fps + 0.001);
      if (
        !player.select(target) ||
        (clip.motion && (audio.current.seeking || audio.current.readyState < 2))
      ) {
        setReady(false);
        if (
          !view ||
          view.clip.audio !== clip.audio ||
          target < (view.mediaOffset ?? 0) * clip.fps ||
          target >= (view.until ?? Math.ceil(view.clip.duration * clip.fps))
        )
          return;
      } else {
        setReady(true);
      }
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
        if (Math.abs(video.currentTime - (i / c.fps - offset)) > 0.001) {
          video.currentTime = Math.max(0, i / c.fps - offset);
        }
      } else {
        if (
          Math.abs(video.currentTime - (audio.current.currentTime - offset)) >
          1 / c.fps
        ) {
          video.currentTime = Math.max(0, audio.current.currentTime - offset);
        }
        if (video.paused) video.play().catch(() => {});
      }
    } else {
      if (!force && frame === undefined && view.frame === i) return;
      renderer.current.draw(c.start + i / c.fps);
    }
    view.frame = i;
    canvas.current.dataset.frame = i;
    const ms = Math.round((c.start + i / c.fps) * 1000);
    if (clock.current) {
      clock.current.textContent =
        Math.floor(ms / 60000) +
        ":" +
        ((ms % 60000) / 1000).toFixed(3).padStart(6, "0");
    }
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
    const snapshot = preview.current;
    const { values: snapValues, composition: snapComp } = snapshot;
    const seq = ++latest.current;
    const changed =
      structureKey(snapComp) !== structureKey(proposal.composition) ||
      Object.entries(snapValues).some(
        ([key, value]) =>
          !(key in materialDefaults) && value !== proposal.values[key],
      );
    const clip =
      changed && proposal.clip.edit_segment_frames
        ? { ...proposal.clip, segment_frames: proposal.clip.edit_segment_frames }
        : proposal.clip;
    const unavailable = Object.entries(proposal.fonts || {}).find(
      ([field, fonts]) => !fonts.includes(snapValues[field]),
    );
    if (unavailable) {
      setReady(false);
      setStatus("字体不可用，请重新选择 " + snapValues[unavailable[0]]);
      return;
    }
    if (clip.segment_frames) {
      const media = audio.current;
      const previous = presented.current;
      setReady(false);
      if (media.getAttribute("src") !== clip.audio) {
        const position =
          previous && previous.clip.audio !== clip.audio
            ? previous.clip.start + previous.frame / previous.clip.fps - clip.start
            : (clip.entry_frame || 0) / clip.fps;
        media.src = clip.audio;
        media.currentTime = Math.max(0, Math.min(position, clip.duration));
      }
      const player = segmentPlayer({
        proposal: { ...proposal, clip },
        snapshot,
        currentSnapshot: () => preview.current,
        geometry: geometryKey,
        keepPlaying: !!previous && previous.clip.audio === clip.audio && changed,
        direction,
        media,
        api,
        requestPreview,
        resume,
        hookCache: segmentHooks.current,
        canvas: canvas.current,
        fallback: fallback.current,
        renderer: () => (renderer.current ??= createRenderer(canvas.current)),
        present: (view) => {
          presented.current = view;
          setNativeActive(!!view.fallback);
          setReady(true);
        },
        redraw: () => draw(undefined, true),
        status: setStatus,
        active: () => latest.current === seq,
      });
      segments.current = { player, clip };
      draw();
      return () => {
        player.stop();
        segments.current = null;
        ++latest.current;
      };
    }

    const geometry = { ...snapValues, ...materialDefaults };
    const key = geometryKey;
    setReady(false);
    const hit = cached.current.get(key);

    async function apply() {
      try {
        let hook = hit;
        if (
          !hook &&
          structureKey(snapComp) === structureKey(proposal.composition) &&
          JSON.stringify(geometry) ===
            JSON.stringify({ ...proposal.values, ...materialDefaults })
        ) {
          hook = proposal.hook;
        }
        if (!hook) {
          ({ hook } = await requestPreview(
            () =>
              api("render", {
                version: proposal.version,
                direction,
                ...snapshot,
              }),
            () => seq === latest.current,
          ));
        }
        cached.current.set(key, hook);
        if (seq !== latest.current) return;
        let native;
        try {
          renderer.current ??= createRenderer(canvas.current);
          const activate = await renderer.current.prepare(
            hook,
            clip.background,
            clip.motion,
          );
          if (seq !== latest.current) return;
          activate();
          const live = preview.current;
          renderer.current.setParameters(
            materialValues(proposal, live.values, live.composition),
          );
        } catch {
          setStatus("正在生成原生预渲染片段");
          native = await nativeFrame(
            fallback.current,
            (snap) =>
              api("native", { version: proposal.version, direction, ...snap }),
            () => preview.current,
            () => seq === latest.current,
            (a, b) => a.values === b.values && a.composition === b.composition,
          );
          if (!native) return;
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
        canvas.current.hidden = !!native;
        fallback.current.hidden = !native;
        const displayed = native?.values ?? preview.current;
        presented.current = {
          clip,
          hook,
          version: proposal.version,
          direction,
          ...displayed,
          frame: -1,
          fallback: native?.video,
        };
        setNativeActive(!!native);
        setReady(true);
        draw(undefined, true);
        setStatus(native ? "原生预渲染片段" : "实时预览");
        canvas.current.dataset.hook = hook;
        canvas.current.dataset.values = JSON.stringify(displayed.values);
        if (resume.current) {
          resume.current = false;
          audio.current.play().catch(() => {});
        }
      } catch (e) {
        if (seq === latest.current) setStatus(e.message);
      }
    }

    if (!hit && changed) setStatus("正在更新当前片段");
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
  }, [proposal, renderKey, connection, direction]);

  useEffect(() => {
    const view = presented.current;
    if (
      !view ||
      view.fallback ||
      view.version !== proposal?.version ||
      view.direction !== direction
    )
      return;
    const changed = Object.keys(values).filter(
      (name) => values[name] !== view.values[name],
    );
    if (
      structureKey(view.composition) !== structureKey(previewComposition) ||
      (!changed.length && view.composition === previewComposition) ||
      changed.some((name) => !(name in materialDefaults))
    )
      return;
    renderer.current?.setParameters(
      materialValues(proposal, values, previewComposition),
    );
    view.values = values;
    view.composition = previewComposition;
    canvas.current.dataset.values = JSON.stringify(values);
    draw(undefined, true);
  }, [proposal, values, previewComposition, direction]);

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

  function matchesCurrent(v) {
    return (
      ready &&
      v?.version === proposal?.version &&
      v?.direction === direction &&
      sameValues(v.values, values) &&
      compositionKey(v.composition) === compositionKey(composition)
    );
  }

  async function grab() {
    if (trial) return;
    const v = presented.current;
    if (!matchesCurrent(v)) return;
    audio.current.pause();
    const target = v.frame / v.clip.fps;
    const media = audio.current;
    if (Math.abs(media.currentTime - target) > 0.00001) media.currentTime = target;
    if (v.clip.motion && media.seeking) {
      await new Promise((resolve) =>
        media.addEventListener("seeked", resolve, { once: true }),
      );
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
      const ctx = pixels.getContext("2d");
      ctx.drawImage(
        v.fallback ? fallback.current : media,
        0,
        0,
        pixels.width,
        pixels.height,
      );
      if (!v.fallback) {
        ctx.drawImage(canvas.current, 0, 0, pixels.width, pixels.height);
      }
    }
    setCompare(null);
    setCapture({
      width: pixels.width,
      height: pixels.height,
      image: pixels.toDataURL(),
      values: v.values,
      composition: v.composition,
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
    if (trial || busy || gestures.current || !matchesCurrent(v)) return;
    const data = {
      action,
      base: state.version,
      version: v.version,
      direction: v.direction,
      values: v.values,
      composition: v.composition,
      hook: v.hook,
      clip: v.clip.id,
      frame: v.frame,
      time: v.clip.start + v.frame / v.clip.fps,
      note,
      frames,
    };
    const fingerprint = JSON.stringify({
      ...data,
      frame: undefined,
      time: undefined,
    });
    if (receipt.current?.fingerprint !== fingerprint) {
      receipt.current = {
        fingerprint,
        payload: { ...data, token: crypto.randomUUID() },
      };
    }
    setBusy(true);
    try {
      await api("submit", receipt.current.payload);
      receipt.current = null;
      setStatus(
        action === "accept"
          ? "已采用这版"
          : action === "continue"
            ? "已保存交接"
            : "意见已保存",
      );
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
    if (!presented.current || capture || libraryOpen) return;
    if (audio.current.paused) {
      audio.current.play().catch((e) => setStatus(e.message));
    } else {
      audio.current.pause();
    }
  }

  // Global keyboard shortcuts (Space, Left/Right, S, Ctrl/Cmd+Z, Escape)
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") {
        if (libraryOpen) {
          setLibraryOpen(false);
          e.preventDefault();
          return;
        }
        if (trial && !capture) {
          finishTrial();
          e.preventDefault();
          return;
        }
      }
      if (
        (e.ctrlKey || e.metaKey) &&
        !e.shiftKey &&
        e.key.toLowerCase() === "z" &&
        !e.target.closest('input:not([type="range"]), textarea, [contenteditable]') &&
        undoCount > 0 &&
        !state?.accepted &&
        !capture &&
        !libraryOpen
      ) {
        e.preventDefault();
        undo();
        return;
      }
      if (
        !ready ||
        capture ||
        libraryOpen ||
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
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    const sync = () =>
      setFullscreen(document.fullscreenElement?.id === "review-playback");
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);

  // Effects actions (shared between left persistent rack & right effects panel)
  const activeEffectTrack =
    tracks && (tracks[effectTrack] ? effectTrack : Object.keys(tracks)[0]);

  function buildTrialGraph(node) {
    if (!composition || !proposal?.component_schema || !activeEffectTrack)
      return composition;
    const items = trackEffectItems(composition, activeEffectTrack);
    let next = placeEffect(
      composition,
      activeEffectTrack,
      items,
      proposal.component_schema,
      node,
    );
    const original = items.find((item) => item.node.id === node.id)?.node;
    for (const key of Object.keys(node.bindings)) {
      if (original && original.values[key] !== node.values[key]) {
        next = componentValue(next, node.id, key, node.values[key]);
      }
    }
    return next;
  }

  function auditionEffect(node) {
    const schema = proposal.component_schema;
    const nextGraph = buildTrialGraph(node);
    setTrialNode(node);
    setTrial({
      graph: nextGraph,
      label: title(schema[node.component].label),
      finish: finishTrial,
      apply: () => {
        finishTrial();
        editComposition(nextGraph);
        setSelectedEffectId(node.id);
      },
    });
  }

  function placeEffectAction(item, position) {
    if (!composition || !proposal?.component_schema || !activeEffectTrack) return;
    const schema = proposal.component_schema;
    const items = trackEffectItems(composition, activeEffectTrack);
    const node =
      item.node ?? {
        ...makeNode(item.kind, schema[item.kind]),
        target: item.target,
      };
    const same =
      !item.node &&
      occupants(items, schema, item.kind, node.target).find(
        ({ node: old }) =>
          old.component === item.kind && old.target === node.target,
      );
    if (same) {
      finishTrial();
      setEditTab("effects");
      setSelectedEffectId(same.node.id);
      return;
    }
    finishTrial();
    editComposition(
      placeEffect(
        composition,
        activeEffectTrack,
        items,
        schema,
        node,
        position,
      ),
    );
  }

  function removeEffectAction(node) {
    if (!composition) return;
    finishTrial();
    editComposition({
      ...composition,
      groups: composition.groups.map((group) => ({
        ...group,
        components: group.components.filter((item) => item.id !== node.id),
      })),
    });
    if (selectedEffectId === node.id) setSelectedEffectId(null);
  }

  function inspectEffectFromRack(node) {
    finishTrial();
    setEditTab("effects");
    setPanelOpen(true);
    setSelectedEffectId(node.id);
  }

  function jumpTo(time) {
    if (!proposal?.clip) return;
    audio.current.currentTime = Math.max(
      0,
      Math.min(proposal.clip.duration, time - proposal.clip.start),
    );
    draw(undefined, true);
  }

  const clip = proposal?.clip;
  const Media = clip?.motion ? "video" : "audio";
  const revision = state?.revisions[proposal?.version - 1];
  const allCandidates = revision
    ? [revision, ...(revision.directions ?? [])]
    : [];
  const canCompare = allCandidates.length > 1;
  const previewing =
    !!composition &&
    (workspaceMode ?? (canCompare ? "preview" : "edit")) === "preview";
  const inEditor = !previewing;

  const updating = !ready && status === "正在更新当前片段";
  const canSubmit =
    matchesCurrent(presented.current) &&
    !busy &&
    !state?.accepted &&
    !gestures.current &&
    !trial;
  const canReset =
    !!composition &&
    (compositionKey(composition) !== compositionKey(proposal?.composition) ||
      !sameValues(values, proposal?.values));

  const percentOf = proposal?.percent_of ?? {};
  const sizeFields = new Set(Object.values(percentOf));

  function renderLegacyField(f) {
    const reference = percentOf[f.name];
    const live = f.name in materialDefaults;
    return (
      <Field
        key={f.name}
        field={f}
        fonts={proposal.fonts?.[f.name]}
        sample={proposal.sample}
        value={values[f.name]}
        referenceSize={rangeDrafts[reference] ?? values[reference]}
        onDraft={
          sizeFields.has(f.name) || live
            ? (draft) => {
                if (sizeFields.has(f.name)) {
                  setRangeDrafts((cur) => ({ ...cur, [f.name]: draft }));
                }
                if (live && draft != null) changeValue(f.name, draft, false);
              }
            : undefined
        }
        onCommit={live ? (value) => changeValue(f.name, value) : undefined}
        change={(value) => changeValue(f.name, value)}
      />
    );
  }

  const focus = proposal?.focus;
  const groups = proposal?.groups || {};
  const grouped = new Set(Object.values(groups).flat());

  function renderLegacyFields(list) {
    return (
      <div className="property-groups">
        {Object.entries(groups).map(([groupTitle, ids]) => {
          const members = list.filter((f) => ids.includes(f.name));
          return members.length ? (
            <section className="property-group" key={groupTitle}>
              <div className="property-heading">
                <h3>{groupTitle}</h3>
              </div>
              <div className="property-fields">
                {members.map(renderLegacyField)}
              </div>
            </section>
          ) : null;
        })}
        {list.some((f) => !grouped.has(f.name)) && (
          <div className="property-fields">
            {list
              .filter((f) => !grouped.has(f.name))
              .map(renderLegacyField)}
          </div>
        )}
      </div>
    );
  }

  // Single unified status text & dot state
  const statusText = state?.accepted
    ? "已采用此版本"
    : state?.working
      ? "正在修订中…"
      : !ready
        ? status || "正在更新…"
        : status === "实时预览" && state?.saved?.action === "feedback"
          ? "意见已保存 · 实时预览"
          : status === "实时预览" && state?.saved?.action === "continue"
            ? "已保存交接 · 实时预览"
            : status;
  const statusState =
    updating || !ready || state?.working ? "busy" : "ready";

  const hasEdits = (candidate, index) => {
    const key = revision.version + ":" + index;
    const draft = drafts.current.get(key)?.snapshot ?? state.drafts?.[key];
    return (
      !!draft &&
      (compositionKey(draft.composition) !==
        compositionKey(candidate.composition) ||
        !sameValues(draft.values, candidate.values))
    );
  };

  return (
    <div className="studio-shell">
      {/* ====================================================================
          Single-Row Studio Topbar
         ==================================================================== */}
      <header className="topbar">
        <div className="topbar-brand">
          <span className="brand-mark">Kara</span>
          <h1 className="topbar-title" title={state?.title || "样式评审"}>
            {state?.title || "打开评审"}
          </h1>

          <div className="topbar-pickers">
            {canCompare && (
              <Select
                value={String(direction)}
                items={allCandidates.map((p, i) => ({
                  value: String(i),
                  label: p.title || p.template || `候选 ${i + 1}`,
                }))}
                onValueChange={(value) => {
                  const idx = Number(value);
                  if (!Number.isNaN(idx) && idx !== direction) {
                    choose(revision, null, idx);
                  }
                }}
              >
                <SelectTrigger size="sm" aria-label="切换候选方向">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="start">
                  {allCandidates.map((p, i) => (
                    <SelectItem key={i} value={String(i)}>
                      {p.title || p.template || `候选 ${i + 1}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {state && state.revisions.length > 1 && (
              <Select
                value={String(proposal?.version ?? state.version)}
                items={state.revisions.map((p) => ({
                  value: String(p.version),
                  label: `第 ${p.version} 版`,
                }))}
                onValueChange={(value) =>
                  value && choose(state.revisions[Number(value) - 1])
                }
              >
                <SelectTrigger size="sm" aria-label="切换方案版本">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="start">
                  {state.revisions.map((p) => (
                    <SelectItem key={p.version} value={String(p.version)}>
                      第 {p.version} 版
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        </div>

        {composition && (
          <div className="topbar-center">
            <nav className="segmented" aria-label="工作模式">
              <button
                type="button"
                aria-pressed={previewing}
                onClick={() => setWorkspaceMode("preview")}
              >
                预览
              </button>
              <button
                type="button"
                aria-pressed={inEditor}
                onClick={() => setWorkspaceMode("edit")}
              >
                编辑
              </button>
            </nav>
          </div>
        )}

        <div className="topbar-actions">
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            title="收藏与个人偏好"
            aria-label="收藏与个人偏好"
            onClick={() => setLibraryOpen(true)}
          >
            <Bookmark />
          </button>

          {(inEditor || canCompare) && (
            <button
              type="button"
              className="btn btn-ghost btn-icon"
              title={
                previewing
                  ? panelOpen
                    ? "收起候选栏"
                    : "展开候选栏"
                  : panelOpen
                    ? "收起右侧面板"
                    : "展开右侧面板"
              }
              aria-label={panelOpen ? "收起侧栏" : "展开侧栏"}
              aria-expanded={panelOpen}
              onClick={() => setPanelOpen((v) => !v)}
            >
              {panelOpen ? <PanelRightClose /> : <PanelRightOpen />}
            </button>
          )}

          <span className="topbar-divider" aria-hidden="true" />

          {state?.accepted ? (
            <span className="accepted-pill">
              <Check />
              已采用
            </span>
          ) : (
            <>
              {composition && (
                <button
                  type="button"
                  className="btn"
                  disabled={!canSubmit}
                  title="交接当前草稿作为下一轮迭代的基础，后续编辑仍保存为草稿"
                  onClick={() => submit("continue")}
                >
                  以这套继续
                </button>
              )}
              <button
                type="button"
                className="btn btn-primary"
                disabled={!canSubmit}
                title="确定当前方案为最终交付版本，用于整曲导出"
                onClick={() => submit("accept")}
              >
                采用这版
              </button>
            </>
          )}
        </div>
      </header>

      {/* ====================================================================
          Main Workspace (Preview Mode OR Edit Mode)
         ==================================================================== */}
      <main
        ref={layout.workspace}
        className={"workspace " + (previewing ? "mode-preview" : "mode-edit")}
        data-wide={layout.wide}
        data-shelf={previewing && canCompare && panelOpen}
        data-panel-open={panelOpen}
        style={{
          "--monitor-width": layout.width + "px",
          "--frame-ratio": (clip?.width || 1280) / (clip?.height || 720),
        }}
      >
        {/* Left Column: Video Monitor + Persistent Effects Rack (in Edit Mode) */}
        <div className="monitor-column">
          <div id="review-playback" className="player-region">
            <div className="player-card">
              <div
                className="screen"
                onClick={toggle}
                onWheel={(e) => {
                  if (
                    !capture &&
                    !libraryOpen &&
                    audio.current?.paused &&
                    !e.ctrlKey &&
                    e.deltaY
                  ) {
                    step(Math.sign(e.deltaY));
                  }
                }}
              >
                <media-controller id="clock-controller" audio="" nohotkeys="">
                  <Media
                    playsInline
                    ref={audio}
                    slot="media"
                    loop
                    onPause={() => {
                      fallback.current?.pause();
                      draw();
                    }}
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
                {compare && (
                  <>
                    <img className="original" src={compare.annotated} />
                    <div
                      className="compare-banner"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span>正在对照历史截帧</span>
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => setCompare(null)}
                      >
                        退出对照
                      </button>
                    </div>
                  </>
                )}
              </div>

              {/* Single Consolidated Trial Bar inside Monitor */}
              {trial && (
                <div className="trial-bar" role="status">
                  <span className="trial-bar-info">
                    <span className="trial-bar-dot" />
                    正在试放 · {trial.label}
                  </span>
                  <div className="trial-bar-actions">
                    {inEditor && trialNode && (
                      <button
                        type="button"
                        className="btn btn-sm btn-ghost"
                        onClick={() => {
                          setEditTab("effects");
                          setPanelOpen(true);
                          setSelectedEffectId("__trial__");
                        }}
                      >
                        <SlidersHorizontal />
                        调参
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-sm btn-ghost"
                      onClick={trial.finish}
                    >
                      <X />
                      退出
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm btn-warn"
                      onClick={trial.apply}
                    >
                      <Plus />
                      添加到草稿
                    </button>
                  </div>
                </div>
              )}

              <div className="transport">
                <media-control-bar mediacontroller="clock-controller">
                  <media-play-button />
                  <button
                    type="button"
                    aria-label="上一帧"
                    title="上一帧 (←)"
                    disabled={!ready}
                    onClick={() => step(-1)}
                  >
                    <StepBack />
                  </button>
                  <button
                    type="button"
                    aria-label="下一帧"
                    title="下一帧 (→)"
                    disabled={!ready}
                    onClick={() => step(1)}
                  >
                    <StepForward />
                  </button>
                  <media-time-range
                    onKeyDown={(e) => {
                      if (
                        e.code !== "Space" ||
                        e.ctrlKey ||
                        e.altKey ||
                        e.metaKey ||
                        e.isComposing ||
                        capture
                      )
                        return;
                      e.preventDefault();
                      if (!e.repeat) toggle();
                    }}
                  />
                  <span className="playback-clock" ref={clock} />
                  <media-mute-button />
                  <media-volume-range />
                  <button
                    type="button"
                    aria-label="截帧提意见"
                    title="截帧提意见 (S)"
                    disabled={!ready || !!trial}
                    onClick={grab}
                  >
                    <Camera />
                  </button>
                  {compare && (
                    <button
                      type="button"
                      aria-label="退出历史对照"
                      title="退出历史对照"
                      onClick={() => setCompare(null)}
                    >
                      <Layers />
                    </button>
                  )}
                  <button
                    type="button"
                    aria-label={fullscreen ? "退出全屏" : "全屏"}
                    title={fullscreen ? "退出全屏" : "全屏"}
                    onClick={(e) =>
                      fullscreen
                        ? document.exitFullscreen()
                        : e.currentTarget
                            .closest(".player-region")
                            .requestFullscreen()
                    }
                  >
                    {fullscreen ? <Minimize /> : <Maximize />}
                  </button>
                </media-control-bar>
              </div>

              <div className="status-strip">
                <output role="status">
                  <span className="status-dot" data-state={statusState} />
                  <span>{statusText}</span>
                </output>
                <span className="status-hints">
                  Space 播放 · ←/→ 逐帧 · S 截帧
                </span>
              </div>
            </div>
          </div>

          {/* Persistent Left Effects Rack in Edit Mode (stable across all right tabs) */}
          {inEditor && panelOpen && composition && tracks && (
            <EffectsRack
              graph={composition}
              schema={proposal.component_schema}
              tracks={tracks}
              track={activeEffectTrack}
              onTrackChange={(nextTrack) => {
                finishTrial();
                setEffectTrack(nextTrack);
                setSelectedEffectId(null);
              }}
              selectedId={selectedEffectId}
              disabled={!!state?.accepted}
              onInspect={inspectEffectFromRack}
              onRemove={removeEffectAction}
              onReorder={(node, position) =>
                placeEffectAction({ node }, position)
              }
            />
          )}
        </div>

        {/* Preview Mode: Full-Height Candidate Shelf */}
        {previewing && canCompare && panelOpen && (
          <aside className="preview-shelf" id="preview-candidates">
            <CandidateCards
              revision={revision}
              direction={direction}
              api={api}
              choose={(index) => {
                if (direction !== index) choose(revision, null, index);
              }}
              edit={() => setWorkspaceMode("edit")}
              hasEdits={hasEdits}
            />
          </aside>
        )}

        {/* Edit Mode: Center Resizer */}
        {inEditor && layout.wide && panelOpen && (
          <div
            className="workspace-resizer"
            role="separator"
            aria-label="调整画面与编辑区宽度"
            aria-orientation="vertical"
            aria-valuemin={layout.min}
            aria-valuemax={layout.max}
            aria-valuenow={layout.width}
            tabIndex={0}
            {...layout.separator}
          />
        )}

        {/* Edit Mode: Right Panel (Single Level Tabs: 样式 | 特效 | 意见) */}
        {inEditor && (
          <aside className="editor-panel" hidden={!panelOpen}>
            <div className="panel-header">
              <nav className="panel-tabs" aria-label="编辑分区">
                <button
                  type="button"
                  className="panel-tab"
                  aria-pressed={editTab === "style"}
                  onClick={() => setEditTab("style")}
                >
                  <Type />
                  样式
                </button>
                {composition && (
                  <button
                    type="button"
                    className="panel-tab"
                    aria-pressed={editTab === "effects"}
                    onClick={() => setEditTab("effects")}
                  >
                    <Layers3 />
                    特效
                  </button>
                )}
                <button
                  type="button"
                  className="panel-tab"
                  aria-pressed={editTab === "feedback"}
                  onClick={() => setEditTab("feedback")}
                >
                  <MessageSquare />
                  意见
                  {frames.length > 0 && (
                    <span className="tab-badge">{frames.length}</span>
                  )}
                </button>
              </nav>

              {composition && (
                <div className="panel-tools">
                  {saveStatus && (
                    <span className="draft-hint" aria-live="polite">
                      {saveStatus}
                    </span>
                  )}
                  <button
                    type="button"
                    className="btn btn-ghost btn-icon btn-sm"
                    disabled={!undoCount || !!state?.accepted}
                    title="撤销 (Ctrl+Z)"
                    aria-label="撤销上一次编辑"
                    onClick={undo}
                  >
                    <Undo2 />
                  </button>
                  {canReset && !state?.accepted && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      title="恢复该候选最初的样式和特效"
                      onClick={resetComposition}
                    >
                      <RotateCcw />
                      重置
                    </button>
                  )}
                </div>
              )}
            </div>

            <div className="panel-body">
              {editTab === "style" && (
                <>
                  {composition ? (
                    tracksError ? (
                      <p className="fx-empty">{tracksError}</p>
                    ) : !tracks ? (
                      <p className="fx-empty">正在读取字幕声部…</p>
                    ) : !Object.keys(tracks).length ? (
                      <p className="fx-empty">此评审区间没有可编辑声部。</p>
                    ) : (
                      <PropertyEditor
                        key={`${proposal.version}:${direction}`}
                        graph={composition}
                        baseline={proposal.composition}
                        tracks={tracks}
                        schema={proposal.component_schema}
                        sample={proposal.sample}
                        edit={editComposition}
                        jumpTo={jumpTo}
                        disabled={!!state?.accepted}
                      />
                    )
                  ) : (
                    <div className="legacy-section">
                      {canCompare && (
                        <div className="legacy-directions">
                          {allCandidates.map((p, i) => (
                            <button
                              key={i}
                              type="button"
                              className="legacy-direction-btn"
                              aria-pressed={direction === i}
                              onClick={() => choose(revision, null, i)}
                              style={{
                                "--direction-accent": [
                                  "#32b38c",
                                  "#ebb052",
                                  "#a78bfa",
                                ][i % 3],
                              }}
                            >
                              <strong>{p.title || p.template}</strong>
                              {p.summary && <small>{p.summary}</small>}
                            </button>
                          ))}
                        </div>
                      )}
                      {!canCompare && proposal?.summary && (
                        <p className="legacy-summary">{proposal.summary}</p>
                      )}
                      {proposal?.not_inherited?.length > 0 && (
                        <p className="legacy-summary">
                          新模板未继承：{proposal.not_inherited.join("、")}
                        </p>
                      )}
                      {proposal?.presets?.length > 0 && (
                        <div className="legacy-presets">
                          {proposal.presets.map((p) => (
                            <button
                              key={p.title}
                              type="button"
                              className="btn btn-sm"
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
                      {renderLegacyFields(
                        (proposal?.parameters || []).filter(
                          (f) => !focus?.length || focus.includes(f.name),
                        ),
                      )}
                      {focus?.length > 0 && (
                        <details className="studio-details">
                          <summary>
                            <ChevronRight />
                            全部参数
                          </summary>
                          <div className="studio-details-body">
                            {renderLegacyFields(
                              proposal.parameters.filter(
                                (f) => !focus.includes(f.name),
                              ),
                            )}
                          </div>
                        </details>
                      )}
                    </div>
                  )}
                </>
              )}

              {editTab === "effects" && composition && (
                tracksError ? (
                  <p className="fx-empty">{tracksError}</p>
                ) : !tracks ? (
                  <p className="fx-empty">正在读取字幕声部…</p>
                ) : !Object.keys(tracks).length ? (
                  <p className="fx-empty">此评审区间没有可编辑声部。</p>
                ) : (
                  <EffectsPanel
                    graph={composition}
                    schema={proposal.component_schema}
                    tracks={tracks}
                    track={activeEffectTrack}
                    selectedId={selectedEffectId}
                    onSelectId={setSelectedEffectId}
                    trialNode={trialNode}
                    onAudition={auditionEffect}
                    onFinishTrial={finishTrial}
                    onPlace={placeEffectAction}
                    edit={editComposition}
                    sample={proposal.sample}
                    disabled={!!state?.accepted}
                  />
                )
              )}

              {editTab === "feedback" && (
                <div className="feedback-panel">
                  {frames.length > 0 ? (
                    <div className="feedback-frames">
                      {frames.map((f, i) => (
                        <div className="frame-card" key={i}>
                          <img src={f.annotated} alt={`截帧 ${i + 1}`} />
                          <textarea
                            className="studio-textarea"
                            aria-label="编辑批注"
                            placeholder="补充这帧的修改意见…"
                            value={f.note}
                            onChange={(e) =>
                              setFrames(
                                frames.map((item, j) =>
                                  i === j
                                    ? { ...item, note: e.target.value }
                                    : item,
                                ),
                              )
                            }
                          />
                          <button
                            type="button"
                            className="btn btn-danger-ghost btn-icon btn-sm"
                            aria-label="移除截帧"
                            title="移除截帧"
                            onClick={() =>
                              setFrames(frames.filter((_, j) => i !== j))
                            }
                          >
                            <Trash2 />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="feedback-empty">
                      在播放器中按 <strong>S</strong> 或点击相机图标，可截帧框选具体画面问题并附到这里。
                    </div>
                  )}

                  <div className="feedback-compose">
                    <textarea
                      className="studio-textarea"
                      aria-label="修改意见"
                      placeholder="描述整体想调整的地方…"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                    />
                    <div className="feedback-compose-actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={!canSubmit || (!note.trim() && !frames.length)}
                        onClick={() => submit("feedback")}
                      >
                        提交修改意见
                      </button>
                    </div>
                  </div>

                  {history.length > 0 && (
                    <div className="history-list">
                      <h3>历史记录</h3>
                      {history.map((h) => (
                        <section className="history-entry" key={h.id}>
                          <div className="history-entry-header">
                            <strong>
                              第 {h.version} 版 ·{" "}
                              {h.action === "accept"
                                ? "已采用"
                                : h.action === "continue"
                                  ? "继续此方向"
                                  : "修改意见"}
                            </strong>
                          </div>
                          {h.note && <p>{h.note}</p>}
                          {h.frames?.map((f, i) => (
                            <button
                              key={i}
                              type="button"
                              className="history-frame-btn"
                              onClick={() => {
                                audio.current.pause();
                                audio.current.currentTime = f.time - clip.start;
                                draw(
                                  Math.round((f.time - clip.start) * clip.fps),
                                );
                                setCapture(null);
                                setCompare(f);
                              }}
                            >
                              <img src={f.annotated} alt="" />
                              <span>
                                {f.time.toFixed(3)}s · {f.note || "点击对照此帧"}
                              </span>
                            </button>
                          ))}
                        </section>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </aside>
        )}
      </main>

      {/* ====================================================================
          Centered Annotation Lightbox Modal
         ==================================================================== */}
      {capture && (
        <Annotation
          key={capture.time + "-" + capture.version}
          frame={capture}
          onAdd={(f) => {
            setFrames([...frames, f]);
            setCapture(null);
            finishTrial();
            setWorkspaceMode("edit");
            setPanelOpen(true);
            setEditTab("feedback");
          }}
          onClose={() => setCapture(null)}
        />
      )}

      {/* ====================================================================
          Secondary Library & Preferences Modal
         ==================================================================== */}
      {libraryOpen && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="收藏与个人偏好"
          onClick={(e) => {
            if (e.target === e.currentTarget) setLibraryOpen(false);
          }}
        >
          <div className="modal-dialog modal-dialog-sm">
            <div className="modal-header">
              <h2>收藏与个人偏好</h2>
              <button
                type="button"
                className="btn btn-ghost btn-icon btn-sm"
                aria-label="关闭"
                onClick={() => setLibraryOpen(false)}
              >
                <X />
              </button>
            </div>
            <div className="modal-body">
              <Library
                api={api}
                ready={ready}
                canSave={ready && !composition}
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

createRoot(document.querySelector("#root")).render(<App />);
