/* ================================================================
   Enhanced WebGL Orb Renderer — Upgraded Visuals & Animation
   ================================================================ */

class OrbRenderer {
    constructor(container, opts = {}) {
        this.container = container;
        this.hue = opts.hue ?? 0;
        this.hoverIntensity = opts.hoverIntensity ?? 0.2;
        this.bgColor = opts.backgroundColor ?? [0.02, 0.02, 0.06];

        // Animation state with smoother interpolation
        this.targetHover = 0;
        this.currentHover = 0;
        this.currentRot = 0;
        this.lastTs = 0;

        // New: Breathing animation state
        this.breathPhase = 0;
        this.targetBreath = 0;
        this.currentBreath = 0;

        // New: Color cycling
        this.colorCycle = 0;
        this.colorCycleSpeed = 0.1;

        this.canvas = document.createElement('canvas');
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.container.appendChild(this.canvas);

        this.gl = this.canvas.getContext('webgl', { 
            alpha: true, 
            premultipliedAlpha: false, 
            antialias: false 
        });
        if (!this.gl) { console.warn('WebGL not available'); return; }

        this._build();
        this._resize();
        this._onResize = this._resize.bind(this);
        window.addEventListener('resize', this._onResize);
        this._raf = requestAnimationFrame(this._loop.bind(this));
    }

    /* =============================================================
       ENHANCED VERTEX SHADER
       ============================================================= */
    static VERT = `
    precision highp float;
    attribute vec2 position;
    attribute vec2 uv;
    varying vec2 vUv;
    void main(){ 
        vUv = uv; 
        gl_Position = vec4(position, 0.0, 1.0); 
    }`;

    /* =============================================================
       ENHANCED FRAGMENT SHADER — Richer colors, smoother noise,
       improved lighting, and organic animation
       ============================================================= */
    static FRAG = `
    precision highp float;
    uniform float iTime;
    uniform vec3  iResolution;
    uniform float hue;
    uniform float hover;
    uniform float rot;
    uniform float hoverIntensity;
    uniform vec3  backgroundColor;
    uniform float breath;
    uniform float colorCycle;
    varying vec2  vUv;

    /* ----- Color-space conversion: RGB ↔ YIQ ----- */
    vec3 rgb2yiq(vec3 c){
        float y = dot(c, vec3(.299, .587, .114));
        float i = dot(c, vec3(.596, -.274, -.322));
        float q = dot(c, vec3(.211, -.523, .312));
        return vec3(y, i, q);
    }
    vec3 yiq2rgb(vec3 c){
        return vec3(
            c.x + .956 * c.y + .621 * c.z,
            c.x - .272 * c.y - .647 * c.z,
            c.x - 1.106 * c.y + 1.703 * c.z
        );
    }

    vec3 adjustHue(vec3 color, float hueDeg){
        float h = hueDeg * 3.14159265 / 180.0;
        vec3 yiq = rgb2yiq(color);
        float cosA = cos(h);
        float sinA = sin(h);
        float i2 = yiq.y * cosA - yiq.z * sinA;
        float q2 = yiq.y * sinA + yiq.z * cosA;
        yiq.y = i2;
        yiq.z = q2;
        return yiq2rgb(yiq);
    }

    /* ----- Enhanced 3D Simplex Noise with smoother hash ----- */
    vec3 hash33(vec3 p3){
        p3 = fract(p3 * vec3(0.1031, 0.11369, 0.13787));
        p3 += dot(p3, p3.yxz + 19.19);
        return -1.0 + 2.0 * fract(vec3(
            p3.x + p3.y, 
            p3.x + p3.z, 
            p3.y + p3.z
        ) * p3.zyx);
    }

    float snoise3(vec3 p){
        const float K1 = 0.333333333;
        const float K2 = 0.166666667;
        vec3 i = floor(p + (p.x + p.y + p.z) * K1);
        vec3 d0 = p - (i - (i.x + i.y + i.z) * K2);
        vec3 e = step(vec3(0.0), d0 - d0.yzx);
        vec3 i1 = e * (1.0 - e.zxy);
        vec3 i2 = 1.0 - e.zxy * (1.0 - e);
        vec3 d1 = d0 - (i1 - K2);
        vec3 d2 = d0 - (i2 - K1);
        vec3 d3 = d0 - 0.5;
        vec4 h = max(0.6 - vec4(
            dot(d0, d0), 
            dot(d1, d1), 
            dot(d2, d2), 
            dot(d3, d3)
        ), 0.0);
        vec4 n = h * h * h * h * vec4(
            dot(d0, hash33(i)),
            dot(d1, hash33(i + i1)),
            dot(d2, hash33(i + i2)),
            dot(d3, hash33(i + 1.0))
        );
        return dot(vec4(31.316), n);
    }

    /* ----- Multi-octave noise for richer detail ----- */
    float fbm3(vec3 p){
        float value = 0.0;
        float amplitude = 0.5;
        float frequency = 1.0;
        for(int i = 0; i < 4; i++){
            value += amplitude * snoise3(p * frequency);
            amplitude *= 0.5;
            frequency *= 2.0;
        }
        return value;
    }

    vec4 extractAlpha(vec3 c){
        float a = max(max(c.r, c.g), c.b);
        return vec4(c / (a + 1e-5), a);
    }

    /* ----- Enhanced color palette with more vibrancy ----- */
    const vec3 baseColor1 = vec3(0.65, 0.35, 1.0);      // Richer purple
    const vec3 baseColor2 = vec3(0.25, 0.85, 0.95);   // Brighter cyan
    const vec3 baseColor3 = vec3(0.08, 0.12, 0.7);    // Deep blue-violet
    const vec3 baseColor4 = vec3(1.0, 0.4, 0.6);      // New: Soft pink accent

    const float innerRadius = 0.55;   // Slightly smaller for more glow
    const float noiseScale = 0.75;    // Adjusted for finer detail

    /* ----- Improved lighting with multiple falloff types ----- */
    float light1(float i, float a, float d){
        return i / (1.0 + d * a);
    }
    float light2(float i, float a, float d){
        return i / (1.0 + d * d * a);
    }
    float light3(float i, float a, float d){
        return i * exp(-d * a);  // New: Exponential falloff for sharper highlights
    }

    /* ----- Enhanced draw function with richer visuals ----- */
    vec4 draw(vec2 uv){
        // Dynamic hue shift based on time and colorCycle
        float dynamicHue = hue + colorCycle * 30.0;
        vec3 c1 = adjustHue(baseColor1, dynamicHue);
        vec3 c2 = adjustHue(baseColor2, dynamicHue);
        vec3 c3 = adjustHue(baseColor3, dynamicHue);
        vec3 c4 = adjustHue(baseColor4, dynamicHue + 60.0);  // Offset pink

        float ang = atan(uv.y, uv.x);
        float len = length(uv);
        float invLen = len > 0.0 ? 1.0 / len : 0.0;

        float bgLum = dot(backgroundColor, vec3(0.299, 0.587, 0.114));

        // Enhanced noise with multiple layers
        float timeScale = iTime * 0.4;
        float n0 = fbm3(vec3(uv * noiseScale, timeScale)) * 0.5 + 0.5;
        float n1 = snoise3(vec3(uv * noiseScale * 1.5, timeScale * 1.2)) * 0.5 + 0.5;

        // Breathing effect on radius
        float breathMod = 1.0 + breath * 0.08 * sin(iTime * 1.5);
        float r0 = mix(
            mix(innerRadius, 1.0, 0.35),
            mix(innerRadius, 1.0, 0.55),
            n0
        ) * breathMod;

        float d0 = distance(uv, (r0 * invLen) * uv);
        float v0 = light1(1.2, 8.0, d0);
        v0 *= smoothstep(r0 * 1.08, r0, len);

        // Enhanced inner fade with noise
        float innerFade = smoothstep(r0 * 0.75, r0 * 0.92, len);
        float innerNoise = snoise3(vec3(ang * 3.0, len * 5.0, iTime * 0.3)) * 0.5 + 0.5;
        v0 *= mix(innerFade, 1.0, bgLum * 0.6 + innerNoise * 0.2);

        // Multiple orbiting lights for richer highlights
        float a2 = iTime * -0.8;
        vec2 pos1 = vec2(cos(a2), sin(a2)) * r0 * 0.85;
        float d1 = distance(uv, pos1);
        float v1 = light2(1.8, 4.0, d1);
        v1 *= light1(1.0, 40.0, d0);

        // Secondary orbiting light
        float a3 = iTime * 0.6 + 2.094;  // 120 degrees offset
        vec2 pos2 = vec2(cos(a3), sin(a3)) * r0 * 0.7;
        float d2 = distance(uv, pos2);
        float v1b = light3(0.8, 6.0, d2);
        v1b *= light1(0.8, 30.0, d0);

        // Combine lights
        v1 += v1b;

        // Enhanced radial masks
        float v2 = smoothstep(1.0, mix(innerRadius, 1.0, n0 * 0.4), len);
        float v3 = smoothstep(innerRadius, mix(innerRadius, 1.0, 0.45), len);

        // Color blending with angular variation and noise
        float cl = cos(ang + iTime * 1.5) * 0.5 + 0.5;
        float cl2 = sin(ang * 2.0 + iTime * 0.7) * 0.5 + 0.5;
        vec3 colBase = mix(c1, c2, cl);
        colBase = mix(colBase, c4, cl2 * 0.3);  // Subtle pink injection

        float fadeAmt = mix(1.0, 0.12, bgLum);

        // Dark composite with more depth
        vec3 darkCol = mix(c3, colBase, v0);
        darkCol = mix(darkCol, c4, v1 * 0.15);  // Pink highlights
        darkCol = (darkCol + v1) * v2 * v3;
        darkCol = clamp(darkCol, 0.0, 1.0);

        // Light composite with better blending
        vec3 lightCol = (colBase + v1 * 0.9) * mix(1.0, v2 * v3, fadeAmt);
        lightCol = mix(backgroundColor, lightCol, v0);
        lightCol = clamp(lightCol, 0.0, 1.0);

        // Final mix with background luminance
        vec3 fc = mix(darkCol, lightCol, bgLum);

        // Add subtle outer glow
        float outerGlow = smoothstep(1.2, 0.8, len) * 0.15;
        fc += c1 * outerGlow * (0.5 + 0.5 * sin(iTime * 2.0));

        return extractAlpha(fc);
    }

    vec4 mainImage(vec2 fragCoord){
        vec2 center = iResolution.xy * 0.5;
        float sz = min(iResolution.x, iResolution.y);
        vec2 uv = (fragCoord - center) / sz * 2.0;

        // Apply rotation with smoother motion
        float s2 = sin(rot);
        float c2 = cos(rot);
        uv = vec2(c2 * uv.x - s2 * uv.y, s2 * uv.x + c2 * uv.y);

        /// Enhanced wavy distortion with breathing
        float waveIntensity = hover * hoverIntensity * (1.0 + breath * 0.3);
        uv.x += waveIntensity * 0.08 * sin(uv.y * 12.0 + iTime * 1.2);
        uv.y += waveIntensity * 0.08 * sin(uv.x * 12.0 + iTime * 1.2 + 1.047);

        // Additional subtle distortion
        uv += snoise3(vec3(uv * 0.5, iTime * 0.2)) * 0.02 * hover;

        return draw(uv);
    }

    void main(){
        vec2 fc = vUv * iResolution.xy;
        vec4 col = mainImage(fc);
        gl_FragColor = vec4(col.rgb * col.a, col.a);
    }
    \`;

    _compile(type, src) {
        const gl = this.gl;
        const s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
            console.error('Shader compile error:', gl.getShaderInfoLog(s));
            gl.deleteShader(s);
            return null;
        }
        return s;
    }

    _build() {
        const gl = this.gl;
        const vs = this._compile(gl.VERTEX_SHADER, OrbRenderer.VERT);
        const fs = this._compile(gl.FRAGMENT_SHADER, OrbRenderer.FRAG);
        if (!vs || !fs) return;

        this.pgm = gl.createProgram();
        gl.attachShader(this.pgm, vs);
        gl.attachShader(this.pgm, fs);
        gl.linkProgram(this.pgm);
        if (!gl.getProgramParameter(this.pgm, gl.LINK_STATUS)) {
            console.error('Program link error:', gl.getProgramInfoLog(this.pgm));
            return;
        }
        gl.useProgram(this.pgm);

        const posLoc = gl.getAttribLocation(this.pgm, 'position');
        const uvLoc = gl.getAttribLocation(this.pgm, 'uv');

        const posBuf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
        gl.enableVertexAttribArray(posLoc);
        gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

        const uvBuf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, uvBuf);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 2, 0, 0, 2]), gl.STATIC_DRAW);
        gl.enableVertexAttribArray(uvLoc);
        gl.vertexAttribPointer(uvLoc, 2, gl.FLOAT, false, 0, 0);

        // Enhanced uniforms including new ones
        this.u = {};
        [
            'iTime', 'iResolution', 'hue', 'hover', 'rot', 
            'hoverIntensity', 'backgroundColor', 'breath', 'colorCycle'
        ].forEach(name => {
            this.u[name] = gl.getUniformLocation(this.pgm, name);
        });

        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.clearColor(0, 0, 0, 0);
    }

    _resize() {
        const dpr = window.devicePixelRatio || 1;
        const w = this.container.clientWidth;
        const h = this.container.clientHeight;
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        if (this.gl) this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    }

    _loop(ts) {
        this._raf = requestAnimationFrame(this._loop.bind(this));
        if (!this.pgm) return;

        const gl = this.gl;
        const t = ts * 0.001;
        const dt = this.lastTs ? t - this.lastTs : 0.016;
        this.lastTs = t;

        // Smoother hover interpolation
        this.currentHover += (this.targetHover - this.currentHover) * Math.min(dt * 3.5, 1);

        // Rotation with variable speed based on activity
        const rotSpeed = this.currentHover > 0.5 ? 0.5 : 0.15;
        if (this.currentHover > 0.3) this.currentRot += dt * rotSpeed;

        // Breathing animation
        this.breathPhase += dt * 1.2;
        this.targetBreath = this.currentHover > 0.5 ? 1.0 : 0.3;
        this.currentBreath += (this.targetBreath - this.currentBreath) * Math.min(dt * 2.0, 1);

        // Color cycling
        this.colorCycle += dt * this.colorCycleSpeed;

        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.useProgram(this.pgm);

        gl.uniform1f(this.u.iTime, t);
        gl.uniform3f(this.u.iResolution, this.canvas.width, this.canvas.height, this.canvas.width / this.canvas.height);
        gl.uniform1f(this.u.hue, this.hue);
        gl.uniform1f(this.u.hover, this.currentHover);
        gl.uniform1f(this.u.rot, this.currentRot);
        gl.uniform1f(this.u.hoverIntensity, this.hoverIntensity);
        gl.uniform3f(this.u.backgroundColor, this.bgColor[0], this.bgColor[1], this.bgColor[2]);
        gl.uniform1f(this.u.breath, this.currentBreath * Math.sin(this.breathPhase) * 0.5 + 0.5);
        gl.uniform1f(this.u.colorCycle, this.colorCycle);

        gl.drawArrays(gl.TRIANGLES, 0, 3);
    }

    setActive(active) {
        this.targetHover = active ? 1.0 : 0.0;
        const ctn = this.container;
        if (active) ctn.classList.add('active');
        else ctn.classList.remove('active');
    }

    destroy() {
        cancelAnimationFrame(this._raf);
        window.removeEventListener('resize', this._onResize);
        if (this.canvas.parentNode) this.canvas.parentNode.removeChild(this.canvas);
        const ext = this.gl.getExtension('WEBGL_lose_context');
        if (ext) ext.loseContext();
    }
}
