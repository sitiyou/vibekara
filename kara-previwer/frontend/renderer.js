export function materialValues(proposal, values) {
  return Object.fromEntries((proposal.material_fields ?? []).map(name => [name, values[name]]));
}

export function sameValues(left, right) {
  return Object.keys(left).length === Object.keys(right).length
    && Object.keys(left).every(name => left[name] === right[name]);
}

export async function nativeFrame(media, request, currentValues, valid) {
  while (valid()) {
    const values = currentValues();
    const {video} = await request(values);
    if (!valid()) break;
    if (!sameValues(values, currentValues())) continue;
    if (media.getAttribute("src") !== video || media.readyState < 2) {
      await new Promise((resolve, reject) => {
        const events = new AbortController();
        media.addEventListener("loadeddata", () => {
          events.abort();
          resolve();
        }, {signal: events.signal});
        media.addEventListener("error", () => {
          events.abort();
          reject(Error("视频缓冲失败"));
        }, {signal: events.signal});
        media.src = video;
      }).catch(error => {
        if (valid()) throw error;
      });
    }
    if (valid() && sameValues(values, currentValues())) return {video, values};
  }
  return null;
}

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
  async function load(key) {
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
    const parameters = Object.entries(sizes.parameters ?? {});
    const materialUniforms = parameters.flatMap(([, slot]) => slot.uniforms)
      .map(name => `uniform float ${name};`).join("\n");
    const source = materialUniforms + "\n" + frag;
    const program = acquire(programs, source, async () => {
      const p = gl.createProgram();
      const vs = shader(gl.VERTEX_SHADER, vertex);
      const fs = shader(gl.FRAGMENT_SHADER, prefix + source + "\nvoid main(){pixel=hook();}");
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
        parameters: parameters.map(([name, slot]) => ({
          name, kind: slot.kind, defaults: slot.default,
          locations: slot.uniforms.map(symbol => gl.getUniformLocation(p, symbol)),
        })),
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

  function setParameters(values) {
    if (!current) return;
    gl.useProgram(current.p);
    for (const { name, kind, defaults, locations } of current.parameters) {
      const value = values[name];
      let parts = defaults;
      if (kind === "float" && Number.isFinite(value)) parts = [value];
      if (kind === "color" && /^[0-9A-Fa-f]{6}$/.test(value)) {
        parts = value.match(/../g).map(channel => parseInt(channel, 16) / 255);
      }
      parts.forEach((part, index) => gl.uniform1f(locations[index], part));
    }
  }

  return {
    draw,
    setParameters,
    async prepare(key, url, motion = false) {
      if (!cache.has(key))
        cache.set(
          key,
          load(key).catch((error) => {
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
        setParameters({});
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
