import { useEffect, useRef, useState } from "react";

const preferenceKey = "kara-previwer:studio-layout";
const desktopQuery = "(min-width: 960px) and (min-height: 500px)";

function readRatio() {
  try {
    const saved = JSON.parse(localStorage.getItem(preferenceKey));
    if (Number.isFinite(saved?.ratio) && saved.ratio >= 0.3 && saved.ratio <= 0.7) {
      return saved.ratio;
    }
  } catch {}
  return 0.52;
}

export function useWorkspaceLayout() {
  const workspace = useRef(null);
  const resize = useRef(null);
  const [ratio, setRatio] = useState(readRatio);
  const [wide, setWide] = useState(() => matchMedia(desktopQuery).matches);
  const [available, setAvailable] = useState(0);
  const [dragWidth, setDragWidth] = useState(null);

  const min = 360;
  const max = Math.max(min, Math.min(Math.round(available * 0.64), available - 420));
  const clamp = (value) => Math.max(min, Math.min(max, value));
  const fallbackWidth = available > 0 ? Math.round(available * ratio) : 640;
  const width = clamp(dragWidth ?? fallbackWidth);

  useEffect(() => {
    const media = matchMedia(desktopQuery);
    const onChange = (event) => {
      resize.current = null;
      setDragWidth(null);
      setWide(event.matches);
    };
    const observer = new ResizeObserver(([entry]) => {
      setAvailable(Math.floor(entry.contentRect.width));
    });
    if (workspace.current) observer.observe(workspace.current);
    media.addEventListener("change", onChange);
    return () => {
      observer.disconnect();
      media.removeEventListener("change", onChange);
    };
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(preferenceKey, JSON.stringify({ ratio }));
    } catch {}
  }, [ratio]);

  function commitWidth(nextWidth) {
    const clamped = clamp(nextWidth);
    if (available > 0) setRatio(clamped / available);
  }

  function endResize(event, save = false) {
    const drag = resize.current;
    if (!drag || drag.id !== event.pointerId) return;
    resize.current = null;
    setDragWidth(null);
    if (save) commitWidth(drag.width);
  }

  function onKeyDown(event) {
    const step = event.shiftKey ? 48 : 16;
    let next = null;
    if (event.key === "ArrowLeft") next = width - step;
    else if (event.key === "ArrowRight") next = width + step;
    else if (event.key === "Home") next = min;
    else if (event.key === "End") next = max;
    if (next === null) return;
    event.preventDefault();
    commitWidth(next);
  }

  return {
    workspace,
    wide,
    min,
    max,
    width,
    resizing: dragWidth !== null,
    separator: {
      onKeyDown,
      onPointerDown(event) {
        if (event.button !== 0 || resize.current) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        resize.current = { id: event.pointerId, x: event.clientX, start: width, width };
        setDragWidth(width);
      },
      onPointerMove(event) {
        const drag = resize.current;
        if (!drag || drag.id !== event.pointerId) return;
        drag.width = clamp(drag.start + (event.clientX - drag.x));
        setDragWidth(drag.width);
      },
      onPointerUp: (event) => endResize(event, true),
      onPointerCancel: (event) => endResize(event, false),
      onLostPointerCapture: (event) => endResize(event, false),
    },
  };
}
