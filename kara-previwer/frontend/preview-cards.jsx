import { useEffect, useRef, useState } from "react";
import { ArrowRight, Pause, Play } from "lucide-react";

export function MotionPreview({
  poster,
  src,
  load,
  label,
  auto = true,
  loadVisible = false,
  startAt = 0,
}) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [manual, setManual] = useState(null);
  const [reduced, setReduced] = useState(
    () => matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [foreground, setForeground] = useState(() => !document.hidden);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.45 },
    );
    if (ref.current) observer.observe(ref.current);
    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const onMotion = (event) => setReduced(event.matches);
    const onVisibility = () => setForeground(!document.hidden);
    query.addEventListener("change", onMotion);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      observer.disconnect();
      query.removeEventListener("change", onMotion);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const active = foreground && visible && (manual ?? (auto && !reduced));

  useEffect(() => {
    if ((active || (loadVisible && foreground && visible)) && !src) load?.();
  }, [active, src, load, visible, foreground, loadVisible]);

  useEffect(() => {
    const video = ref.current?.querySelector("video");
    if (!video) return;
    if (active) video.play().catch(() => {});
    else video.pause();
  }, [active, src]);

  return (
    <div className="motion-preview" ref={ref}>
      {(src || poster) && (
        <video
          src={src || undefined}
          poster={poster}
          muted
          playsInline
          loop
          preload="none"
          aria-hidden="true"
          onLoadedMetadata={(event) => {
            const video = event.currentTarget;
            if (startAt > 0 && startAt < video.duration) {
              video.currentTime = startAt;
            }
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        />
      )}
      {(src || load) && (
        <button
          type="button"
          className="preview-play"
          onClick={(e) => {
            e.stopPropagation();
            setManual(!playing);
          }}
          aria-label={(playing ? "暂停" : "播放") + label + "预览"}
        >
          {playing ? <Pause /> : <Play />}
        </button>
      )}
    </div>
  );
}

function CandidateCard({ proposal, chosen, edited, choose, edit, endpoint, api }) {
  const [media, setMedia] = useState(null);
  const requested = useRef(false);
  const title = proposal.title || proposal.template;

  function load() {
    if (requested.current) return;
    requested.current = true;
    api(endpoint)
      .then(setMedia)
      .catch(() => setMedia(false));
  }

  return (
    <li className="candidate-card" data-chosen={chosen}>
      <div onClick={choose} style={{ cursor: "pointer" }}>
        <MotionPreview
          poster={media?.poster ?? proposal.clip.background}
          src={media?.video}
          load={media === false ? undefined : load}
          label={title}
          loadVisible
        />
      </div>
      <div className="candidate-card-body">
        <button
          type="button"
          className="candidate-choice"
          aria-pressed={chosen}
          onClick={choose}
        >
          <div className="candidate-title-row">
            <strong>{title}</strong>
            {edited && <span className="candidate-edited">已编辑</span>}
          </div>
          {proposal.summary && (
            <span className="candidate-summary">{proposal.summary}</span>
          )}
        </button>
      </div>
    </li>
  );
}

export function CandidateCards({ revision, direction, api, choose, edit, hasEdits }) {
  const all = [revision, ...revision.directions];
  return (
    <section className="candidate-browser" aria-labelledby="candidate-heading">
      <div className="candidate-heading">
        <h2 id="candidate-heading">
          候选方向<span className="candidate-count">{all.length}</span>
        </h2>
        <button type="button" className="btn btn-sm btn-primary" onClick={edit}>
          进入编辑 <ArrowRight />
        </button>
      </div>
      <ul className="candidate-cards">
        {all.map((proposal, index) => (
          <CandidateCard
            key={revision.version + ":" + index}
            proposal={proposal}
            chosen={direction === index}
            edited={hasEdits(proposal, index)}
            choose={() => choose(index)}
            edit={() => {
              if (direction !== index) choose(index);
              edit();
            }}
            endpoint={`candidate-card?version=${revision.version}&direction=${index}`}
            api={api}
          />
        ))}
      </ul>
    </section>
  );
}
