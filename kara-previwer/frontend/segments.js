// A scheduler is scoped to one revision and one set of selected values.
export function segmentPlayer({ proposal, values, direction, api, requestPreview, renderer, media,
  canvas, fallback, present, redraw, status, buffered, active, resume, hookCache }) {
  const clip = proposal.clip, fps = clip.fps, width = clip.segment_frames;
  const count = Math.ceil(clip.duration * fps);
  const entries = new Map();
  let wanted = -1, showing = -1, lookahead = -1, serial = 0, stopped = false;
  const valid = () => !stopped && active();
  const geometry = JSON.stringify([proposal.version, direction, {...values, ...proposal.palette}]);
  function requestHook(first, prefetch) {
    const key = geometry + ":" + first;
    const hit = hookCache.get(key);
    if (hit) return hit;
    return requestPreview(() => {
      let request = hookCache.get(key);
      if (!request) {
        request = api("render", {version: proposal.version, direction, values, frame: first, prefetch});
        hookCache.set(key, request);
        request.catch(() => hookCache.delete(key));
      }
      return request;
    }, () => valid() && (first === wanted || (prefetch && first === wanted + width)), prefetch);
  }
  function load(first, prefetch = false) {
    if (entries.has(first)) return entries.get(first);
    const payload = {version: proposal.version, direction, values, frame: first, prefetch};
    const promise = (async () => {
      const {hook} = await requestHook(first, prefetch);
      if (!valid()) return;
      if (!prefetch && first === wanted) prefetchNext(first);
      let activate, video;
      try {
        const r = renderer();
        activate = await r.prepare(hook, clip.background, proposal.palette, values, clip.motion);
      } catch {
        video = (await api("native", payload)).video;
      }
      if (!valid()) return;
      buffered(first, Math.min(first + width, count));
      return {activate, video, hook};
    })();
    entries.set(first, promise);
    promise.catch(() => entries.delete(first));
    return promise;
  }
  function prefetchNext(first) {
    const next = first + width;
    if (lookahead === first || next >= count) return;
    lookahead = first;
    load(next, true).catch(() => {});
  }
  async function switchTo(first) {
    const token = ++serial;
    wanted = first;

    // Cached chunks activate in a microtask, before the next paint.
    const timer = setTimeout(() => {
      if (!valid() || first !== wanted || token !== serial) return;
      if (!media.paused) { resume.current = true; media.pause(); }
      status("正在缓冲字幕");
    }, 35);
    try {
      if (!valid() || token !== serial) return;
      const entry = await load(first);
      if (!valid() || token !== serial) return;
      if (entry.video) {
        if (!media.paused) { resume.current = true; media.pause(); }
        await new Promise((resolve, reject) => {
          fallback.onloadeddata = resolve;
          fallback.onerror = () => reject(Error("视频缓冲失败"));
          fallback.src = entry.video;
        });
      }
      if (!valid() || token !== serial) return;
      entry.activate?.();
      canvas.hidden = !!entry.video;
      fallback.hidden = !entry.video;
      showing = first;
      present({clip, hook: entry.hook, version: proposal.version, direction, values,
        fallback: entry.video, mediaOffset: first / fps, frame: -1});
      canvas.dataset.hook = entry.hook;
      canvas.dataset.values = JSON.stringify(values);
      status(entry.video ? "原生分段预览" : "实时预览");
      redraw();
      if (resume.current) { resume.current = false; media.play().catch(() => {}); }
      for (const key of entries.keys()) if (Math.abs(key - first) > width) entries.delete(key);
    } catch (e) {
      if (valid() && token === serial) { status(e.message); wanted = -1; }
    } finally { clearTimeout(timer); }
  }
  return {
    select(frame) {
      const first = Math.floor(Math.min(count - 1, Math.max(0, frame)) / width) * width;
      if (first !== wanted) switchTo(first);
      if (!media.paused || resume.current) prefetchNext(first);
      return first === showing && first === wanted;
    },
    stop() { stopped = true; serial++; },
  };
}
