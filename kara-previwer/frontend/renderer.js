export function createRenderer(canvas) {
  const gl = canvas.getContext("webgl2", { alpha: true, premultipliedAlpha: true, antialias: false });
  if (!gl) throw Error("此浏览器无法使用 WebGL 2");
  let current, imageUrl;
  const cache = new Map();
  const programs = new Map();
  const texturesByHash = new Map();
  const parallel = gl.getExtension("KHR_parallel_shader_compile");

  function acquire(pool, key, create, dispose) {
    let entry = pool.get(key);
    if (!entry) {
      entry = { value: Promise.resolve().then(create), references: 0 };
      pool.set(key, entry);
    }
    entry.references++;
    return {
      value: entry.value,
      release() {
        if (--entry.references === 0) {
          pool.delete(key);
          entry.value.then(dispose, () => {});
        }
      },
    };
  }
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  const vertex = `#version 300 es
out vec2 uv;
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2); uv=vec2(p.x,1.-p.y); gl_Position=vec4(2.*p-1.,0.,1.);}`;
  const prefix = `#version 300 es
precision highp float; precision highp int; precision highp sampler2D;
in vec2 uv; out vec4 pixel;
uniform sampler2D bgTex,KARAMASK,KARADATA; uniform float PTS; uniform bool overlay;
#define HOOKED_tex(p) (overlay ? vec4(0.0) : vec4(texture(bgTex,p).rgb,1.0))
#define HOOKED_pos uv
#define frame 1
`;
  function shader(type, source) {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
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
  const background = texture(0, gl.LINEAR);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
  async function load(key, palette) {
    const base = key + "/";
    async function resource(name) {
      const response = await fetch(base + name);
      if (!response.ok) throw Error("片段加载失败");
      return response;
    }
    const [sizes, frag] = await Promise.all([
      resource("textures.json").then(r => r.json()),
      resource("scene.frag").then(r => r.text()),
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
    const program = acquire(programs, body, async () => {
      const p = gl.createProgram();
      const vs = shader(gl.VERTEX_SHADER, vertex);
      const fs = shader(gl.FRAGMENT_SHADER, prefix + body + "\nvoid main(){pixel=hook();}");
      gl.attachShader(p, vs);
      gl.attachShader(p, fs);
      gl.linkProgram(p);
      try {
        while (parallel && !gl.isContextLost() && !gl.getProgramParameter(p, parallel.COMPLETION_STATUS_KHR)) {
          await new Promise(resolve => setTimeout(resolve, 8));
        }
        if (!gl.getProgramParameter(p, gl.LINK_STATUS))
          throw Error(gl.getShaderInfoLog(fs) || gl.getShaderInfoLog(vs) || gl.getProgramInfoLog(p));
        return p;
      } catch (error) {
        gl.deleteProgram(p);
        throw error;
      } finally {
        gl.deleteShader(vs);
        gl.deleteShader(fs);
      }
    }, p => gl.deleteProgram(p));
    const leases = [program];
    try {
      const p = await program.value;
      const textures = await Promise.all(["KARAMASK", "KARADATA"].map((name, index) => {
        const unit = index + 1;
        const signature = [name, sizes[name], sizes.hashes?.[name] ?? key].join("/");
        const lease = acquire(texturesByHash, signature, async () => {
          const raw = await (await resource(name + ".bin")).arrayBuffer();
          const mask = index === 0;
          const tex = texture(unit, mask ? gl.LINEAR : gl.NEAREST);
          gl.texImage2D(gl.TEXTURE_2D, 0, mask ? gl.R8 : gl.RGBA32F, ...sizes[name],
            0, mask ? gl.RED : gl.RGBA, mask ? gl.UNSIGNED_BYTE : gl.FLOAT,
            mask ? new Uint8Array(raw) : new Float32Array(raw));
          return tex;
        }, tex => gl.deleteTexture(tex));
        leases.push(lease);
        return lease.value;
      }));
      gl.useProgram(p);
      for (const [i, name] of ["bgTex", "KARAMASK", "KARADATA"].entries())
        gl.uniform1i(gl.getUniformLocation(p, name), i);
      return {
        p,
        textures,
        release: () => leases.forEach(lease => lease.release()),
        colors: names.map((name, i) => [
          name,
          gl.getUniformLocation(p, "reviewColor" + i),
        ]),
        time: gl.getUniformLocation(p, "PTS"),
        overlay: gl.getUniformLocation(p, "overlay"),
      };
    } catch (error) {
      leases.forEach(lease => lease.release());
      throw error;
    }
  }
  function draw(pts) {
    if (!current) return;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.useProgram(current.p);
    [background, ...current.textures].forEach((tex, i) => {
      gl.activeTexture(gl.TEXTURE0 + i);
      gl.bindTexture(gl.TEXTURE_2D, tex);
    });
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
      if (!motion && url !== imageUrl) {
        img = new Image();
        img.src = url;
        await img.decode();
      }
      return () => {
        if (img && url !== imageUrl) {
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, background);
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
        gl.uniform1i(scene.overlay, Number(motion));
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
            victim.then(v => v.release(), () => {});
          }
        }
      };
    },
  };
}
