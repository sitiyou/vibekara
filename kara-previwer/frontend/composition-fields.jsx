import { useEffect, useRef } from "react";
import { RotateCcw } from "lucide-react";
import { Field } from "./fields";

export const targets = { track: "整条轨道", body: "正文", ruby: "注音" };

const labels = {
  "Scanline color": "线条颜色",
  Strength: "着色强度",
  Width: "宽度",
  Softness: "柔边",
  "Reading coverage": "注音覆盖",
  "Reverse wipe": "反向走字",
  "Front angle": "倾角",
  "Font family": "字体",
  "Font size": "字号",
  Italic: "斜体",
  Bold: "粗体",
  "Letter spacing": "字距",
  "Primary outline": "主描边",
  "Waiting fill": "唱前填充",
  "Sung fill": "唱后填充",
  "Waiting outline": "唱前描边",
  "Sung outline": "唱后描边",
  Duration: "时长",
  "Timing unit": "过渡单位",
  Color: "颜色",
  Opacity: "不透明度",
  Blur: "模糊",
  Spread: "扩展半径",
  Shadow: "阴影",
  "Horizontal scale": "横向缩放",
  "Vertical scale": "纵向缩放",
  "Reading gap": "注音间距",
  "Reading alignment": "注音对齐",
  Rows: "行数",
  Alignment: "对齐",
  Vertical: "垂直排版",
  "Right to left": "从右到左",
  Scanline: "实色扫描线",
  "Row layout": "行布局",
  "Glyph style": "字体与描边",
  "Steady wipe": "匀速走字",
  "Lyric glow": "歌词辉光",
  "Lyric colors": "唱前与唱后配色",
  "Outline flash": "起音描边闪光",
  "Onset echo": "起音回声",
  "Soft, tinted wipe front": "羽化前沿",
  "Outer outline": "外描边",
  Jump: "跳动",
  "Scale pulse": "缩放弹动",
  Slide: "滑入",
  Fade: "淡入淡出",
  None: "无",
  "Slide out": "滑出",
  "Slide in": "滑入",
  Rise: "上移",
  "Char fade": "逐字淡化",
  "Zoom pulse": "长音缩放",
  "Zoom pulse scanline": "缩放与扫描线",
  "Utopia scanline": "Utopia 弹动与扫描线",
  Twinkle: "漂移星光",
  "Twinkle classic": "呼吸星光",
  "Glyph blur": "字形模糊",
  "Offset shadow": "偏移阴影",
  "Lyric gradient": "歌词渐变",
  "Brighten both sides": "分别提亮前后色",
  "Follow waiting color": "跟随唱前色",
  "Follow sung color": "跟随唱后色",
  "Gradient scanline": "渐变扫描线",
  "First color": "起点颜色",
  "Last color": "终点颜色",
  "Char drip": "逐字倾斜",
  "Spin flip": "旋转翻转",
  "Tilt pop": "倾斜弹入",
  "Tracking in": "字距收拢",
  "Wave in": "波浪入场",
  "Stretch in": "拉伸入场",
  "Glow in": "辉光入场",
  "Assemble in": "粒子聚合",
  Sparkle: "星光迸发",
  Ripple: "涟漪",
  Note: "音符",
  Petal: "花瓣",
  Snow: "镂空雪花",
  "Snow solid": "实心雪花",
  "Scatter out": "径向散开",
  "Converge out": "向中心合拢",
  "Stretch out": "拉伸退场",
  "Glow out": "辉光退场",
  "Dissolve out": "粒子消散",
  "No wipe": "收音时整音节换色",
  "Transition stagger": "逐字错开",
  "Extruded letters": "立体字形",
  "Reading layout": "注音布局",
  "Fade in": "淡入",
  "Fade out": "淡出",
  "Drift out": "漂移退场",
  "Scale tween": "缩放补间",
  "Alternating karaoke rows": "双行交替",
  "Countdown bars": "倒数条",
  "Pulsing volume bars": "脉动音量条",
  "Countdown lamps": "倒数指示灯",
  "Text countdown": "文字倒数",
  "Sparkle emitter": "星光发射器",
  "Falling petals": "飘落花瓣",
  "Back color": "背面颜色",
  Brightness: "亮度",
  Copies: "副本数",
  Direction: "方向",
  "Emissions per second": "每秒发射数",
  Feather: "羽化",
  "Front color": "前沿颜色",
  Height: "高度",
  "Horizontal offset": "水平偏移",
  Origin: "发射位置",
  "Paint layers": "绘制层",
  "Rate multiplier": "密度倍数",
  Scale: "缩放",
  Size: "大小",
  Stagger: "错开比例",
  "Sweep outline color": "描边同步扫色",
  Timing: "生效阶段",
  "Vertical offset": "垂直偏移",
};

const choiceLabels = {
  both: "正文和注音",
  reading: "仅注音",
  preset: "效果默认",
  character: "逐字",
  left: "左对齐",
  center: "居中",
  right: "右对齐",
  alternating: "左右交替",
  line: "整行",
  group: "逐组",
  x: "横向",
  y: "纵向",
  sung: "唱后",
  waiting: "唱前",
  front: "走字前沿",
  solid: "纯色",
  stroke: "描边",
  decor: "装饰",
  all: "全部",
};

export const title = (text) => labels[text] ?? text;

const fieldKinds = { number: "float", integer: "int", boolean: "bool" };

function LiveColor({ name, value, label, onDraft, onCommit }) {
  const input = useRef();
  useEffect(() => {
    const element = input.current;
    const commit = () => onCommit(element.value.slice(1).toUpperCase());
    element.addEventListener("change", commit);
    return () => element.removeEventListener("change", commit);
  }, [onCommit]);

  return (
    <div className="field" data-kind="color">
      <label>{label}</label>
      <div className="field-control">
        <label className="live-color-row">
          <input
            ref={input}
            type="color"
            aria-label={name}
            value={"#" + value}
            onInput={(event) =>
              onDraft(event.currentTarget.value.slice(1).toUpperCase())
            }
          />
          <span className="color-hex">#{value}</span>
        </label>
      </div>
    </div>
  );
}

export function Parameter({
  id,
  name,
  definition,
  value,
  options = {},
  live,
  draft,
  commit,
  sample,
  reset,
  mixed,
}) {
  const [low, high] = options.bounds ?? definition.bounds ?? [];
  const caption = title(options.label || definition.label);

  return (
    <div
      className="composition-parameter"
      data-field={name}
      data-overridden={!!reset}
    >
      {live && definition.kind === "color" ? (
        <LiveColor
          name={caption}
          label={caption}
          value={value}
          onDraft={draft}
          onCommit={commit}
        />
      ) : (
        <Field
          field={{
            name: id + "_" + name,
            caption,
            kind: fieldKinds[definition.kind] ?? definition.kind,
            low,
            high,
            step: options.step ?? definition.step,
            default: value,
            suffix: definition.unit ? " " + definition.unit : "",
            choices: definition.choices,
            labels: definition.choices?.map(
              (option) => choiceLabels[option] ?? option,
            ),
            font: name === "fontname",
          }}
          value={value}
          change={commit}
          onDraft={live ? draft : undefined}
          onCommit={
            live && ["number", "integer"].includes(definition.kind)
              ? commit
              : undefined
          }
          sample={sample}
          compact
        />
      )}
      {reset ? (
        <button
          type="button"
          className="btn btn-ghost btn-icon btn-sm setting-reset"
          onClick={reset}
          aria-label={"恢复" + caption + "的继承值"}
          title="恢复继承值"
        >
          <RotateCcw aria-hidden="true" />
        </button>
      ) : (
        <span />
      )}
      {mixed && <small className="setting-source">各声部的生效值不同</small>}
    </div>
  );
}
