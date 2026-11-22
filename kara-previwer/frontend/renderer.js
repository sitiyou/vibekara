export function createRenderer(canvas) {
  const gl = canvas.getContext("webgl2", { alpha: false, antialias: false });
  if (!gl) throw Error("此浏览器无法使用 WebGL 2");
  let current, background, imageUrl;
  let videoWidth = 0, videoHeight = 0;
  const cache = new Map();
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  const vertex = `#version 300 es
out vec2 uv;
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2); uv=vec2(p.x,1.-p.y); gl_Position=vec4(2.*p-1.,0.,1.);}`;
  const prefix = `#version 300 es
precision highp float; precision highp int; precision highp sampler2D;
in vec2 uv; out vec4 pixel;
uniform sampler2D bgTex,KARAMASK,KARADATA; uniform float PTS;
#define HOOKED_tex(p) texture(bgTex,p)
#define HOOKED_pos uv
#define frame 1
`;
  function shader(type, source) {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS))
      throw Error(gl.getShaderInfoLog(s));
    return s;
  }
  function texture(unit, filter) {
    gl.activeTexture(gl.TEXTURE0 + unit);
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    for (const param of [gl.TEXTURE_MIN_FILTER, gl.TEXTURE_MAG_FILTER])
      gl.texParameteri(gl.TEXTURE_2D, param, filter);
    for (const param of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T])
      gl.texParameteri(gl.TEXTURE_2D, param, gl.CLAMP_TO_EDGE);
    return t;
  }
  async function load(key, palette) {
    const base = key + "/";
    const files = await Promise.all(
      ["textures.json", "scene.frag", "KARAMASK.bin", "KARADATA.bin"].map(
        async (ext) => {
          const r = await fetch(base + ext);
          if (!r.ok) throw Error("片段加载失败");
          return r;
        },
      ),
    );
    const [sizes, frag, mask, data] = await Promise.all([
      files[0].json(),
      files[1].text(),
      files[2].arrayBuffer(),
      files[3].arrayBuffer(),
    ]);
    const limit = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    if ([...sizes.KARAMASK, ...sizes.KARADATA].some(size => size > limit))
      throw Error("字幕纹理超过设备上限");
    const names = Object.keys(palette);
    const uniforms = names
      .map((_, i) => "uniform vec3 reviewColor" + i + ";")
      .join("\n");
    const cases = names
      .map((name, i) => {
        if (!/^[0-9A-Fa-f]{6}$/.test(palette[name]))
          throw Error("无效的模板色值");
        const parts = palette[name]
          .match(/../g)
          .map((v) => parseInt(v, 16) + ".0")
          .join(",");
        return (
          "if(all(lessThan(abs(c-vec3(" +
          parts +
          ")/255.0),vec3(0.00001))))return reviewColor" +
          i +
          ";"
        );
      })
      .join("\n");
    const body = names.length
      ? frag
          .replace("vec3 rgbAt(int i)", "vec3 originalRGB(int i)")
          .replace(
            "int preceding(",
            uniforms +
              "\nvec3 rgbAt(int i){vec3 c=originalRGB(i);" +
              cases +
              "return c;}\nint preceding(",
          )
      : frag;
    const p = gl.createProgram();
    const vs = shader(gl.VERTEX_SHADER, vertex);
    gl.attachShader(p, vs);
    gl.deleteShader(vs);
    const fs = shader(
      gl.FRAGMENT_SHADER,
      prefix + body + "\nvoid main(){pixel=hook();}",
    );
    gl.attachShader(p, fs);
    gl.deleteShader(fs);
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS))
      throw Error(gl.getProgramInfoLog(p));
    gl.useProgram(p);
    const textures = [];
    for (const [i, name, format, raw] of [
      [1, "KARAMASK", gl.R8, mask],
      [2, "KARADATA", gl.RGBA32F, data],
    ]) {
      textures.push(texture(i, i === 1 ? gl.LINEAR : gl.NEAREST));
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        format,
        ...sizes[name],
        0,
        i === 1 ? gl.RED : gl.RGBA,
        i === 1 ? gl.UNSIGNED_BYTE : gl.FLOAT,
        i === 1 ? new Uint8Array(raw) : new Float32Array(raw),
      );
      gl.uniform1i(gl.getUniformLocation(p, name), i);
    }
    return {
      p,
      textures,
      colors: names.map((name, i) => [
        name,
        gl.getUniformLocation(p, "reviewColor" + i),
      ]),
      time: gl.getUniformLocation(p, "PTS"),
    };
  }
  function draw(pts, media) {
    if (!current) return;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.useProgram(current.p);
    [background, ...current.textures].forEach((tex, i) => {
      gl.activeTexture(gl.TEXTURE0 + i);
      gl.bindTexture(gl.TEXTURE_2D, tex);
    });
    if (media && media.readyState >= 2) {
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, background);
      if (media.videoWidth === videoWidth && media.videoHeight === videoHeight) {
        gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, gl.RGBA, gl.UNSIGNED_BYTE, media);
      } else {
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, media);
        videoWidth = media.videoWidth;
        videoHeight = media.videoHeight;
      }
    }
    gl.uniform1f(current.time, pts);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  return {
    draw,
    async prepare(path, url, palette = {}, values = {}, motion = false) {
      const key = path + JSON.stringify(palette);
      if (!cache.has(key))
        cache.set(
          key,
          load(path, palette).catch((error) => {
            cache.delete(key);
            throw error;
          }),
        );
      const scene = await cache.get(key);
      let img;
      if (url !== imageUrl || (!motion && videoWidth)) {
        img = new Image();
        img.src = url;
        await img.decode();
      }
      return () => {
        if (img && (url !== imageUrl || (!motion && videoWidth))) {
          videoWidth = videoHeight = 0;
          if (background) gl.deleteTexture(background);
          background = texture(0, gl.LINEAR);
          gl.texImage2D(
            gl.TEXTURE_2D,
            0,
            gl.RGBA,
            gl.RGBA,
            gl.UNSIGNED_BYTE,
            img,
          );
          imageUrl = url;
        }
        current = scene;
        gl.useProgram(scene.p);
        for (const [name, loc] of scene.colors) {
          const parts = values[name]
            .match(/../g)
            .map((v) => parseInt(v, 16) / 255);
          gl.uniform3fv(loc, parts);
        }
        if (cache.size > 8) {
          const oldest = cache.keys().next().value;
          if (oldest !== key) {
            const victim = cache.get(oldest);
            cache.delete(oldest);
            victim.then((v) => {
              gl.deleteProgram(v.p);
              v.textures.forEach((t) => gl.deleteTexture(t));
            });
          }
        }
      };
    },
  };
}
