import React, { useEffect, useRef, useState } from "react";
import { RotateCcw, X } from "lucide-react";

function mark(ctx, m) {
  const w = ctx.canvas.width;
  const h = ctx.canvas.height;
  ctx.strokeStyle = "#ebb052";
  ctx.lineWidth = Math.max(2, w / 400);
  ctx.shadowColor = "#0e1113";
  ctx.shadowBlur = 3;
  if (m.type === "point") {
    ctx.beginPath();
    ctx.arc(m.x * w, m.y * h, w / 100, 0, 2 * Math.PI);
    ctx.stroke();
  } else {
    ctx.strokeRect(m.x * w, m.y * h, (m.endX - m.x) * w, (m.endY - m.y) * h);
  }
}

export function Annotation({ frame, onAdd, onClose }) {
  const [marks, setMarks] = useState([]);
  const [note, setNote] = useState("");
  const [draft, setDraft] = useState(null);
  const image = useRef();
  const start = useRef();

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function point(e) {
    const r = e.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (e.clientX - r.x) / r.width)),
      y: Math.max(0, Math.min(1, (e.clientY - r.y) / r.height)),
    };
  }

  function shape(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y) < 0.008
      ? { type: "point", ...a }
      : { type: "box", ...a, endX: b.x, endY: b.y };
  }

  function add() {
    const c = document.createElement("canvas");
    c.width = image.current.naturalWidth;
    c.height = image.current.naturalHeight;
    const ctx = c.getContext("2d");
    ctx.drawImage(image.current, 0, 0);
    marks.forEach((m) => mark(ctx, m));
    onAdd({ ...frame, marks, note, annotated: c.toDataURL() });
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="截帧批注"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-dialog">
        <div className="modal-header">
          <h2>
            截帧批注
            <span className="modal-header-hint">
              {frame.time.toFixed(3)}s · 点击打点或拖框标记问题位置
            </span>
          </h2>
          <button
            type="button"
            className="btn btn-ghost btn-icon btn-sm"
            aria-label="关闭截帧批注"
            onClick={onClose}
          >
            <X />
          </button>
        </div>

        <div className="modal-body">
          <div className="capture-stage">
            <div
              className="capture"
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture(e.pointerId);
                start.current = point(e);
              }}
              onPointerMove={(e) => {
                if (start.current) setDraft(shape(start.current, point(e)));
              }}
              onPointerUp={(e) => {
                if (start.current) {
                  setMarks([...marks, shape(start.current, point(e))]);
                }
                start.current = null;
                setDraft(null);
              }}
            >
              <img
                ref={image}
                src={frame.image}
                width={frame.width}
                height={frame.height}
                draggable="false"
              />
              <svg viewBox="0 0 1000 1000" preserveAspectRatio="none">
                {[...marks, ...(draft ? [draft] : [])].map((m, i) =>
                  m.type === "point" ? (
                    <ellipse
                      key={i}
                      cx={m.x * 1000}
                      cy={m.y * 1000}
                      rx="10"
                      ry={(10 * frame.width) / frame.height}
                    />
                  ) : (
                    <rect
                      key={i}
                      x={Math.min(m.x, m.endX) * 1000}
                      y={Math.min(m.y, m.endY) * 1000}
                      width={Math.abs(m.endX - m.x) * 1000}
                      height={Math.abs(m.endY - m.y) * 1000}
                    />
                  ),
                )}
              </svg>
            </div>
          </div>

          <textarea
            className="studio-textarea"
            aria-label="本帧意见"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="描述这一帧想修改的地方（例如：描边偏粗、注音和正文贴得太近）…"
            autoFocus
          />
        </div>

        <div className="modal-footer">
          <div className="modal-footer-left">
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setMarks(marks.slice(0, -1))}
              disabled={!marks.length}
            >
              <RotateCcw />
              撤销标记{marks.length ? ` (${marks.length})` : ""}
            </button>
          </div>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn btn-primary" onClick={add}>
            加入本轮意见
          </button>
        </div>
      </div>
    </div>
  );
}
