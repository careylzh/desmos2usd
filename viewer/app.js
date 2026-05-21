(function () {
  "use strict";

  const canvas = document.getElementById("viewerCanvas");
  const statusText = document.getElementById("statusText");
  const sampleSelect = document.getElementById("sampleSelect");
  const fileInput = document.getElementById("fileInput");
  const panelModeButton = document.getElementById("panelModeButton");
  const fitButton = document.getElementById("fitButton");
  const resetButton = document.getElementById("resetButton");
  const sceneSummary = document.getElementById("sceneSummary");
  const selectionPanel = document.getElementById("selectionPanel");
  const primList = document.getElementById("primList");
  const primFilter = document.getElementById("primFilter");
  const dropOverlay = document.getElementById("dropOverlay");

  const acceptanceRoot = window.location.pathname.includes("/viewer/")
    ? "../artifacts/acceptance"
    : "artifacts/acceptance";
  const fixtureSweepRoot = window.location.pathname.includes("/viewer/")
    ? "../artifacts/fixture_usdz"
    : "artifacts/fixture_usdz";
  const builtInSamples = [
    { key: "zaqxhna15w", label: "zaqxhna15w", url: `${acceptanceRoot}/zaqxhna15w.usda`, group: "Acceptance" },
    { key: "ghnr7txz47", label: "ghnr7txz47", url: `${acceptanceRoot}/ghnr7txz47.usda`, group: "Acceptance" },
    { key: "yuqwjsfvsc", label: "yuqwjsfvsc", url: `${acceptanceRoot}/yuqwjsfvsc.usda`, group: "Acceptance" },
    { key: "vyp9ogyimt", label: "vyp9ogyimt", url: `${acceptanceRoot}/vyp9ogyimt.usda`, group: "Acceptance" },
    { key: "k0fbxxwkqf", label: "k0fbxxwkqf", url: `${acceptanceRoot}/k0fbxxwkqf.usda`, group: "Acceptance" },
  ];
  let sampleCatalog = [];

  const gl = canvas.getContext("webgl2", {
    antialias: true,
    alpha: false,
    preserveDrawingBuffer: true,
  });

  if (!gl) {
    setStatus("WebGL 2 is required for this viewer.");
    return;
  }

  const state = {
    dpr: 1,
    scene: null,
    selectedPrim: -1,
    hiddenPrims: new Set(),
    surfaceMode: "dim",
    camera: {
      yaw: 0.75,
      pitch: 0.55,
      distance: 10,
      target: [0, 0, 0],
      basis: null,
      home: null,
    },
    pointers: new Map(),
    drag: null,
    pickFramebuffer: null,
    pickTexture: null,
    pickDepth: null,
    pickSize: [0, 0],
    programs: createPrograms(gl),
  };

  gl.enable(gl.DEPTH_TEST);
  gl.disable(gl.CULL_FACE);
  gl.clearColor(0.045, 0.045, 0.045, 1);

  bindUi();
  resize();
  updateSurfaceModeButton();
  requestAnimationFrame(render);
  initialize();

  function bindUi() {
    window.addEventListener("resize", resize);

    sampleSelect.addEventListener("change", () => {
      if (!sampleSelect.value) return;
      loadSample(sampleSelect.value, sampleSelect.options[sampleSelect.selectedIndex].textContent);
    });

    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      if (file) loadFile(file);
    });

    panelModeButton.addEventListener("click", () => cycleSurfaceMode());
    fitButton.addEventListener("click", () => fitCamera(true));
    resetButton.addEventListener("click", () => resetCamera());

    primFilter.addEventListener("input", () => renderPrimList());

    canvas.addEventListener("contextmenu", (event) => event.preventDefault());
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("pointercancel", onPointerUp);

    window.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropOverlay.classList.add("active");
    });
    window.addEventListener("dragleave", (event) => {
      if (event.clientX <= 0 || event.clientY <= 0 || event.clientX >= window.innerWidth || event.clientY >= window.innerHeight) {
        dropOverlay.classList.remove("active");
      }
    });
    window.addEventListener("drop", (event) => {
      event.preventDefault();
      dropOverlay.classList.remove("active");
      const file = event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) loadFile(file);
    });
  }

  async function initialize() {
    await populateSampleSelect();
    loadInitialQueryTarget();
  }

  async function populateSampleSelect() {
    const placeholder = sampleSelect.querySelector('option[value=""]');
    sampleSelect.innerHTML = "";
    sampleSelect.appendChild(placeholder || new Option("Select a sample...", ""));
    sampleCatalog = [];

    appendSampleGroup("Acceptance", builtInSamples);

    const fixtureSamples = await loadFixtureSamples();
    if (fixtureSamples.length) {
      appendSampleGroup("Fixture sweep", fixtureSamples);
    }
  }

  function appendSampleGroup(label, samples) {
    if (!samples.length) return;
    const group = document.createElement("optgroup");
    group.label = label;
    for (const sample of samples) {
      const option = document.createElement("option");
      option.value = sample.url;
      option.textContent = sample.label;
      option.dataset.key = normalizeSampleKey(sample.key || sample.label);
      group.appendChild(option);
      sampleCatalog.push(sample);
    }
    sampleSelect.appendChild(group);
  }

  async function loadFixtureSamples() {
    try {
      const response = await fetch(`${fixtureSweepRoot}/summary.json`, { cache: "no-store" });
      if (!response.ok) return [];
      const summary = await response.json();
      if (!summary || !Array.isArray(summary.reports)) return [];
      const seen = new Set();
      return summary.reports
        .filter((report) => report && report.usda_exists && basenameFromPath(report.output))
        .map((report) => {
          const fileName = basenameFromPath(report.output);
          if (!fileName) return null;
          const label = fixtureLabel(report, fileName);
          const url = joinSamplePath(fixtureSweepRoot, fileName);
          const key = `${normalizeSampleKey(label)}
${url}`;
          if (seen.has(key)) return null;
          seen.add(key);
          return {
            key: label,
            label,
            url,
            group: "Fixture sweep",
          };
        })
        .filter(Boolean)
        .sort((left, right) => left.label.localeCompare(right.label));
    } catch (_error) {
      return [];
    }
  }

  function fixtureLabel(report, fileName) {
    if (report && typeof report.fixture === "string" && report.fixture.trim()) {
      return report.fixture.replace(/\.json$/i, "");
    }
    return fileName.replace(/\.usda$/i, "");
  }

  function basenameFromPath(value) {
    if (typeof value !== "string" || !value.trim()) return "";
    const parts = value.split(/[\\/]/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function joinSamplePath(root, fileName) {
    return `${root}/${encodePathSegment(fileName)}`;
  }

  function encodePathSegment(value) {
    return encodeURIComponent(value).replace(/%2F/g, "/");
  }

  function normalizeSampleKey(value) {
    return String(value || "").trim().toLowerCase();
  }

  async function loadSample(url, label) {
    try {
      setStatus(`Loading ${label}...`);
      await nextFrame();
      const response = await fetch(url);
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const text = await response.text();
      await loadUsdaText(text, label.toLowerCase().endsWith(".usda") ? label : `${label}.usda`);
    } catch (error) {
      setStatus(`Could not load sample: ${error.message}`);
    }
  }

  function loadInitialQueryTarget() {
    const params = new URLSearchParams(window.location.search);
    const sample = normalizeSampleKey(params.get("sample") || "");
    if (sample) {
      const option = Array.from(sampleSelect.options).find((candidate) => candidate.dataset.key === sample);
      if (option) {
        sampleSelect.value = option.value;
        loadSample(option.value, option.textContent);
      } else {
        setStatus(`Unknown sample: ${params.get("sample")}`);
      }
      return;
    }

    const usdaPath = (params.get("usda") || "").trim();
    if (!usdaPath) {
      const defaultOption = Array.from(sampleSelect.options).find((option) => option.value);
      if (defaultOption) {
        sampleSelect.value = defaultOption.value;
        loadSample(defaultOption.value, defaultOption.textContent);
      }
      return;
    }
    if (!usdaPath.toLowerCase().endsWith(".usda")) {
      setStatus("The usda query parameter must point to a .usda file.");
      return;
    }
    const label = params.get("label") || usdaPath.split("/").pop() || "sample.usda";
    loadSample(usdaPath, label);
  }

  async function loadFile(file) {
    if (!file.name.toLowerCase().endsWith(".usda")) {
      setStatus("Choose a generated .usda file.");
      return;
    }
    setStatus(`Reading ${file.name}...`);
    await nextFrame();
    const text = await file.text();
    await loadUsdaText(text, file.name);
    sampleSelect.value = "";
  }

  async function loadUsdaText(text, fileName) {
    disposeScene();
    setStatus(`Parsing ${fileName}...`);
    await nextFrame();

    const parsed = parseUsda(text, fileName);
    setStatus(`Building buffers for ${parsed.prims.length.toLocaleString()} prims...`);
    await nextFrame();

    state.scene = buildScene(gl, parsed);
    state.selectedPrim = -1;
    state.hiddenPrims.clear();
    state.surfaceMode = "dim";
    initializeCameraForScene(state.scene);
    updateSurfaceModeButton();
    updateSummary();
    updateSelection();
    renderPrimList();
    const muted = state.scene.stats.reviewMutedCount;
    const reviewNote = muted ? ` ${muted.toLocaleString()} large surface${muted === 1 ? "" : "s"} dimmed for review.` : "";
    setStatus(`Loaded ${fileName}: ${state.scene.stats.meshPrims.toLocaleString()} mesh prims, ${state.scene.stats.faceCount.toLocaleString()} faces.${reviewNote}`);
  }

  function parseUsda(text, fileName) {
    const layer = {};
    const prims = [];
    const lines = text.split(/\r?\n/);
    let inLayerData = false;
    let current = null;

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;

      if (!current && line === "customLayerData = {") {
        inLayerData = true;
        continue;
      }
      if (inLayerData) {
        if (line === "}") {
          inLayerData = false;
          continue;
        }
        const layerMatch = line.match(/^(string|bool|int|double|float)\s+"?([A-Za-z0-9:_-]+)"?\s*=\s*(.+)$/);
        if (layerMatch) layer[layerMatch[2]] = parseUsdValue(layerMatch[3], layerMatch[1]);
        continue;
      }

      const defMatch = line.match(/^def\s+(Mesh|BasisCurves)\s+"([^"]+)"/);
      if (defMatch) {
        current = {
          index: prims.length,
          type: defMatch[1],
          name: defMatch[2],
          metadata: {},
          points: [],
          faceVertexCounts: [],
          faceVertexIndices: [],
          curveVertexCounts: [],
        };
        continue;
      }

      if (!current) continue;

      if (line === "}") {
        current.pointCount = current.points.length;
        current.faceCount = current.faceVertexCounts.length;
        prims.push(current);
        current = null;
        continue;
      }

      const metadataMatch = line.match(/^custom\s+(\w+)\s+([A-Za-z0-9:_-]+)\s*=\s*(.+)$/);
      if (metadataMatch) {
        current.metadata[metadataMatch[2]] = parseUsdValue(metadataMatch[3], metadataMatch[1]);
        continue;
      }

      if (line.startsWith("point3f[] points =")) {
        current.points = parsePoints(line);
      } else if (line.startsWith("int[] faceVertexCounts =")) {
        current.faceVertexCounts = parseInts(line);
      } else if (line.startsWith("int[] faceVertexIndices =")) {
        current.faceVertexIndices = parseInts(line);
      } else if (line.startsWith("int[] curveVertexCounts =")) {
        current.curveVertexCounts = parseInts(line);
      }
    }

    return { fileName, layer, prims };
  }

  function parseUsdValue(rawValue, typeHint) {
    const value = rawValue.trim().replace(/,$/, "");
    if (typeHint === "bool" || value === "true" || value === "false") return value === "true";
    if (typeHint === "int") return Number.parseInt(value, 10);
    if (value.startsWith('"')) {
      try {
        return JSON.parse(value);
      } catch (_error) {
        return value.slice(1, -1);
      }
    }
    return value;
  }

  function parsePoints(line) {
    const points = [];
    const tuplePattern = /\(([^)]+)\)/g;
    let match = tuplePattern.exec(line);
    while (match) {
      const values = match[1].split(",");
      if (values.length >= 3) {
        points.push([
          Number.parseFloat(values[0]),
          Number.parseFloat(values[1]),
          Number.parseFloat(values[2]),
        ]);
      }
      match = tuplePattern.exec(line);
    }
    return points;
  }

  function parseInts(line) {
    const start = line.indexOf("[");
    const end = line.lastIndexOf("]");
    if (start < 0 || end < start) return [];
    const matches = line.slice(start + 1, end).match(/-?\d+/g);
    return matches ? matches.map((value) => Number.parseInt(value, 10)) : [];
  }

  function buildScene(glContext, parsed) {
    const positions = [];
    const colors = [];
    const normals = [];
    const indices = [];
    const linePositions = [];
    const lineColors = [];
    const meshRanges = [];
    const lineRanges = [];
    const prims = [];
    const bounds = createBounds();
    const stats = {
      primCount: parsed.prims.length,
      meshPrims: 0,
      curvePrims: 0,
      pointCount: 0,
      faceCount: 0,
      triangleCount: 0,
      reviewMutedCount: 0,
    };

    for (const prim of parsed.prims) {
      const color = parseColor(prim.metadata["desmos:color"]);
      const hidden = prim.metadata["desmos:hidden"] === true;
      const alpha = hidden ? 90 : 255;
      const primBounds = createBounds();
      const primInfo = {
        index: prim.index,
        type: prim.type,
        name: prim.name,
        metadata: prim.metadata,
        colorHex: rgbToHex(color),
        color,
        sourceAlpha: alpha / 255,
        hiddenInSource: hidden,
        pointCount: prim.points.length,
        faceCount: prim.faceVertexCounts.length,
        triangleCount: 0,
        bounds: primBounds,
        extents: [0, 0, 0],
        diagonal: 0,
        reviewMuted: false,
        reviewReason: "",
        meshRange: null,
        lineRanges: [],
      };

      if (prim.type === "Mesh") {
        stats.meshPrims += 1;
        stats.pointCount += prim.points.length;
        stats.faceCount += prim.faceVertexCounts.length;
        const vertexOffset = positions.length / 3;
        for (const point of prim.points) {
          positions.push(point[0], point[1], point[2]);
          colors.push(color[0], color[1], color[2], alpha);
          normals.push(0, 0, 0);
          expandBounds(bounds, point);
          expandBounds(primBounds, point);
        }

        const indexStart = indices.length;
        let cursor = 0;
        for (const count of prim.faceVertexCounts) {
          const face = prim.faceVertexIndices.slice(cursor, cursor + count);
          cursor += count;
          for (let i = 1; i < face.length - 1; i += 1) {
            const a = vertexOffset + face[0];
            const b = vertexOffset + face[i];
            const c = vertexOffset + face[i + 1];
            indices.push(a, b, c);
            addTriangleNormal(positions, normals, a, b, c);
            primInfo.triangleCount += 1;
          }
        }
        const indexCount = indices.length - indexStart;
        primInfo.meshRange = { primIndex: prim.index, start: indexStart, count: indexCount };
        meshRanges.push(primInfo.meshRange);
        stats.triangleCount += primInfo.triangleCount;
      } else if (prim.type === "BasisCurves") {
        stats.curvePrims += 1;
        stats.pointCount += prim.points.length;
        let pointCursor = 0;
        for (const count of prim.curveVertexCounts) {
          const start = linePositions.length / 3;
          for (let i = 0; i < count; i += 1) {
            const point = prim.points[pointCursor + i];
            if (!point) continue;
            linePositions.push(point[0], point[1], point[2]);
            lineColors.push(color[0], color[1], color[2], alpha);
            expandBounds(bounds, point);
            expandBounds(primBounds, point);
          }
          pointCursor += count;
          const range = { primIndex: prim.index, start, count };
          primInfo.lineRanges.push(range);
          lineRanges.push(range);
        }
      }

      prims.push(primInfo);
    }

    if (!Number.isFinite(bounds.min[0])) {
      expandBounds(bounds, [-1, -1, -1]);
      expandBounds(bounds, [1, 1, 1]);
    }

    // Generate solid hexagonal tubes around every BasisCurves polyline so that
    // curve-heavy scenes (e.g. Eiffel-tower truss diagrams) don't render as a
    // 1-pixel skeleton. WebGL ignores gl.lineWidth > 1 on virtually every
    // browser/driver, so polylines alone look skeletal regardless of the
    // requested line width. Tubes give curves visual weight that matches the
    // way Desmos draws them, without changing the underlying USDA artifact.
    const sceneDiagonal = Math.hypot(
      bounds.max[0] - bounds.min[0],
      bounds.max[1] - bounds.min[1],
      bounds.max[2] - bounds.min[2],
    );
    // Tube radius is a small fraction of the scene diagonal so curves keep visual
    // weight regardless of scene scale. The fraction was tuned against Desmos' own
    // default curve thickness on tower-like scenes (S2-05 Group D); too small and
    // curves still look like a 1-pixel skeleton, too large and adjacent legs fuse.
    const tubeRadius = clamp(sceneDiagonal * 0.006, 0.015, sceneDiagonal * 0.025);
    const tubeSides = 6;
    const tubeRanges = [];
    for (const range of lineRanges) {
      const prim = prims[range.primIndex];
      if (!prim) continue;
      const tubeColor = prim.color;
      const tubeAlpha = Math.round(prim.sourceAlpha * 255);
      const tubeIndexStart = indices.length;
      const polyline = [];
      for (let i = 0; i < range.count; i += 1) {
        const base = (range.start + i) * 3;
        polyline.push([linePositions[base], linePositions[base + 1], linePositions[base + 2]]);
      }
      appendTubeGeometry(positions, colors, normals, indices, polyline, tubeColor, tubeAlpha, tubeRadius, tubeSides);
      const tubeIndexCount = indices.length - tubeIndexStart;
      if (tubeIndexCount > 0) {
        const tubeRange = { primIndex: prim.index, start: tubeIndexStart, count: tubeIndexCount };
        prim.tubeRanges = prim.tubeRanges || [];
        prim.tubeRanges.push(tubeRange);
        tubeRanges.push(tubeRange);
        prim.triangleCount += tubeIndexCount / 3;
        stats.triangleCount += tubeIndexCount / 3;
      }
    }

    normalizeNormals(normals);
    annotateReviewSurfaces(prims, bounds);
    stats.reviewMutedCount = prims.filter((prim) => prim.reviewMuted).length;

    const meshVao = glContext.createVertexArray();
    glContext.bindVertexArray(meshVao);
    const positionBuffer = uploadArrayBuffer(glContext, new Float32Array(positions), 0, 3, glContext.FLOAT, false, 0, 0, state.programs.mesh);
    const colorBuffer = uploadArrayBuffer(glContext, new Uint8Array(colors), 1, 4, glContext.UNSIGNED_BYTE, true, 0, 0, state.programs.mesh);
    const normalBuffer = uploadArrayBuffer(glContext, new Float32Array(normals), 2, 3, glContext.FLOAT, false, 0, 0, state.programs.mesh);
    const indexBuffer = glContext.createBuffer();
    glContext.bindBuffer(glContext.ELEMENT_ARRAY_BUFFER, indexBuffer);
    glContext.bufferData(glContext.ELEMENT_ARRAY_BUFFER, new Uint32Array(indices), glContext.STATIC_DRAW);

    const lineVao = glContext.createVertexArray();
    glContext.bindVertexArray(lineVao);
    const linePositionBuffer = uploadArrayBuffer(glContext, new Float32Array(linePositions), 0, 3, glContext.FLOAT, false, 0, 0, state.programs.line);
    const lineColorBuffer = uploadArrayBuffer(glContext, new Uint8Array(lineColors), 1, 4, glContext.UNSIGNED_BYTE, true, 0, 0, state.programs.line);
    glContext.bindVertexArray(null);

    return {
      fileName: parsed.fileName,
      layer: parsed.layer,
      sourceViewportBounds: parseSourceViewportBounds(parsed.layer),
      sourceViewMetadata: parseSourceViewMetadata(parsed.layer),
      prims,
      stats,
      bounds,
      buffers: {
        meshVao,
        positionBuffer,
        colorBuffer,
        normalBuffer,
        indexBuffer,
        lineVao,
        linePositionBuffer,
        lineColorBuffer,
      },
      meshRanges,
      lineRanges,
      tubeRanges,
      meshIndexCount: indices.length,
      lineVertexCount: linePositions.length / 3,
    };
  }

  function uploadArrayBuffer(glContext, data, location, size, type, normalized, stride, offset) {
    const buffer = glContext.createBuffer();
    glContext.bindBuffer(glContext.ARRAY_BUFFER, buffer);
    glContext.bufferData(glContext.ARRAY_BUFFER, data, glContext.STATIC_DRAW);
    glContext.enableVertexAttribArray(location);
    glContext.vertexAttribPointer(location, size, type, normalized, stride, offset);
    return buffer;
  }

  function addTriangleNormal(positions, normals, a, b, c) {
    const ax = positions[a * 3];
    const ay = positions[a * 3 + 1];
    const az = positions[a * 3 + 2];
    const bx = positions[b * 3];
    const by = positions[b * 3 + 1];
    const bz = positions[b * 3 + 2];
    const cx = positions[c * 3];
    const cy = positions[c * 3 + 1];
    const cz = positions[c * 3 + 2];
    const ux = bx - ax;
    const uy = by - ay;
    const uz = bz - az;
    const vx = cx - ax;
    const vy = cy - ay;
    const vz = cz - az;
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    for (const index of [a, b, c]) {
      normals[index * 3] += nx;
      normals[index * 3 + 1] += ny;
      normals[index * 3 + 2] += nz;
    }
  }

  function normalizeNormals(normals) {
    for (let i = 0; i < normals.length; i += 3) {
      const x = normals[i];
      const y = normals[i + 1];
      const z = normals[i + 2];
      const length = Math.hypot(x, y, z);
      if (length < 1e-20) {
        normals[i] = 0;
        normals[i + 1] = 0;
        normals[i + 2] = 1;
      } else {
        normals[i] = x / length;
        normals[i + 1] = y / length;
        normals[i + 2] = z / length;
      }
    }
  }

  function appendTubeGeometry(positions, colors, normals, indices, polyline, color, alpha, radius, sides) {
    const points = [];
    for (const point of polyline) {
      if (!point) continue;
      const last = points.length ? points[points.length - 1] : null;
      if (last && Math.hypot(point[0] - last[0], point[1] - last[1], point[2] - last[2]) < 1e-9) continue;
      points.push([point[0], point[1], point[2]]);
    }
    if (points.length < 2 || radius <= 0) return;

    const n = points.length;
    const tangents = new Array(n);
    for (let i = 0; i < n; i += 1) {
      let dx;
      let dy;
      let dz;
      if (i === 0) {
        dx = points[1][0] - points[0][0];
        dy = points[1][1] - points[0][1];
        dz = points[1][2] - points[0][2];
      } else if (i === n - 1) {
        dx = points[n - 1][0] - points[n - 2][0];
        dy = points[n - 1][1] - points[n - 2][1];
        dz = points[n - 1][2] - points[n - 2][2];
      } else {
        dx = points[i + 1][0] - points[i - 1][0];
        dy = points[i + 1][1] - points[i - 1][1];
        dz = points[i + 1][2] - points[i - 1][2];
      }
      let len = Math.hypot(dx, dy, dz);
      if (len < 1e-12) {
        tangents[i] = [0, 0, 1];
      } else {
        tangents[i] = [dx / len, dy / len, dz / len];
      }
    }

    function cross(a, b) {
      return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
    }
    function normalize(v) {
      const len = Math.hypot(v[0], v[1], v[2]);
      if (len < 1e-12) return [0, 0, 0];
      return [v[0] / len, v[1] / len, v[2] / len];
    }

    let normal = normalize(cross(tangents[0], [0, 0, 1]));
    if (Math.hypot(normal[0], normal[1], normal[2]) < 0.5) {
      normal = normalize(cross(tangents[0], [1, 0, 0]));
    }
    if (Math.hypot(normal[0], normal[1], normal[2]) < 0.5) {
      normal = normalize(cross(tangents[0], [0, 1, 0]));
    }
    let binormal = normalize(cross(tangents[0], normal));
    if (Math.hypot(binormal[0], binormal[1], binormal[2]) < 0.5) {
      // Final fallback: pick any orthonormal basis (tangent is degenerate).
      normal = [1, 0, 0];
      binormal = [0, 1, 0];
    }

    const frames = [{ n: normal, b: binormal }];
    for (let i = 1; i < n; i += 1) {
      const prev = frames[i - 1];
      // Project the previous normal onto the plane perpendicular to the new tangent
      // (rotation-minimizing frame via simple projection — keeps tube roll continuous).
      const t = tangents[i];
      const dot = prev.n[0] * t[0] + prev.n[1] * t[1] + prev.n[2] * t[2];
      let newN = normalize([prev.n[0] - dot * t[0], prev.n[1] - dot * t[1], prev.n[2] - dot * t[2]]);
      if (Math.hypot(newN[0], newN[1], newN[2]) < 0.5) {
        newN = prev.n;
      }
      const newB = normalize(cross(t, newN));
      frames.push({ n: newN, b: newB });
    }

    const baseVertex = positions.length / 3;
    for (let i = 0; i < n; i += 1) {
      const frame = frames[i];
      for (let s = 0; s < sides; s += 1) {
        const angle = (s / sides) * Math.PI * 2;
        const cs = Math.cos(angle);
        const sn = Math.sin(angle);
        const ox = (frame.n[0] * cs + frame.b[0] * sn) * radius;
        const oy = (frame.n[1] * cs + frame.b[1] * sn) * radius;
        const oz = (frame.n[2] * cs + frame.b[2] * sn) * radius;
        positions.push(points[i][0] + ox, points[i][1] + oy, points[i][2] + oz);
        colors.push(color[0], color[1], color[2], alpha);
        // Outward radial direction is the surface normal.
        const nlen = Math.hypot(ox, oy, oz);
        if (nlen < 1e-12) {
          normals.push(0, 0, 0);
        } else {
          normals.push(ox / nlen, oy / nlen, oz / nlen);
        }
      }
    }

    for (let i = 0; i < n - 1; i += 1) {
      for (let s = 0; s < sides; s += 1) {
        const sNext = (s + 1) % sides;
        const a = baseVertex + i * sides + s;
        const b = baseVertex + i * sides + sNext;
        const c = baseVertex + (i + 1) * sides + sNext;
        const d = baseVertex + (i + 1) * sides + s;
        indices.push(a, b, c, a, c, d);
      }
    }
  }

  function createPrograms(glContext) {
    return {
      mesh: createProgram(glContext, meshVertexShader(), meshFragmentShader(), ["aPosition", "aColor", "aNormal"]),
      line: createProgram(glContext, lineVertexShader(), lineFragmentShader(), ["aPosition", "aColor"]),
      pickMesh: createProgram(glContext, pickVertexShader(), pickFragmentShader(), ["aPosition"]),
      pickLine: createProgram(glContext, pickVertexShader(), pickFragmentShader(), ["aPosition"]),
    };
  }

  function createProgram(glContext, vertexSource, fragmentSource, attributes) {
    const program = glContext.createProgram();
    const vertexShader = compileShader(glContext, glContext.VERTEX_SHADER, vertexSource);
    const fragmentShader = compileShader(glContext, glContext.FRAGMENT_SHADER, fragmentSource);
    glContext.attachShader(program, vertexShader);
    glContext.attachShader(program, fragmentShader);
    attributes.forEach((name, index) => glContext.bindAttribLocation(program, index, name));
    glContext.linkProgram(program);
    if (!glContext.getProgramParameter(program, glContext.LINK_STATUS)) {
      throw new Error(glContext.getProgramInfoLog(program) || "Could not link WebGL program");
    }
    return program;
  }

  function compileShader(glContext, type, source) {
    const shader = glContext.createShader(type);
    glContext.shaderSource(shader, source);
    glContext.compileShader(shader);
    if (!glContext.getShaderParameter(shader, glContext.COMPILE_STATUS)) {
      throw new Error(glContext.getShaderInfoLog(shader) || "Could not compile WebGL shader");
    }
    return shader;
  }

  function meshVertexShader() {
    return `#version 300 es
      in vec3 aPosition;
      in vec4 aColor;
      in vec3 aNormal;
      uniform mat4 uViewProj;
      uniform vec3 uLightDir;
      uniform float uAlphaScale;
      out vec4 vColor;
      void main() {
        float light = 0.54 + 0.46 * abs(dot(normalize(aNormal), normalize(uLightDir)));
        vColor = vec4(aColor.rgb * light, aColor.a * uAlphaScale);
        gl_Position = uViewProj * vec4(aPosition, 1.0);
      }`;
  }

  function meshFragmentShader() {
    return `#version 300 es
      precision mediump float;
      in vec4 vColor;
      uniform vec4 uOverrideColor;
      out vec4 outColor;
      void main() {
        outColor = uOverrideColor.a >= 0.0 ? uOverrideColor : vColor;
      }`;
  }

  function lineVertexShader() {
    return `#version 300 es
      in vec3 aPosition;
      in vec4 aColor;
      uniform mat4 uViewProj;
      uniform float uAlphaScale;
      out vec4 vColor;
      void main() {
        vColor = vec4(aColor.rgb, aColor.a * uAlphaScale);
        gl_Position = uViewProj * vec4(aPosition, 1.0);
      }`;
  }

  function lineFragmentShader() {
    return `#version 300 es
      precision mediump float;
      in vec4 vColor;
      out vec4 outColor;
      void main() {
        outColor = vColor;
      }`;
  }

  function pickVertexShader() {
    return `#version 300 es
      in vec3 aPosition;
      uniform mat4 uViewProj;
      void main() {
        gl_Position = uViewProj * vec4(aPosition, 1.0);
      }`;
  }

  function pickFragmentShader() {
    return `#version 300 es
      precision mediump float;
      uniform vec4 uPickColor;
      out vec4 outColor;
      void main() {
        outColor = uPickColor;
      }`;
  }

  function render() {
    drawScene(false);
    requestAnimationFrame(render);
  }

  function drawScene(isPicking) {
    resize();
    const scene = state.scene;
    const viewProj = computeViewProjection();
    const framebuffer = isPicking ? ensurePickFramebuffer() : null;
    gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(isPicking ? 0 : 0.045, isPicking ? 0 : 0.045, isPicking ? 0 : 0.045, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    if (!scene) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      return;
    }

    if (isPicking) {
      drawPicking(scene, viewProj);
    } else {
      drawVisible(scene, viewProj);
    }

    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }

  function drawVisible(scene, viewProj) {
    if (scene.meshIndexCount > 0) {
      gl.useProgram(state.programs.mesh);
      gl.bindVertexArray(scene.buffers.meshVao);
      gl.uniformMatrix4fv(gl.getUniformLocation(state.programs.mesh, "uViewProj"), false, viewProj);
      gl.uniform3f(gl.getUniformLocation(state.programs.mesh, "uLightDir"), 0.45, 0.7, 0.55);
      gl.uniform4f(gl.getUniformLocation(state.programs.mesh, "uOverrideColor"), 0, 0, 0, -1);

      gl.disable(gl.BLEND);
      gl.depthMask(true);
      for (const prim of scene.prims) {
        if (!shouldDrawPrim(prim) || isTranslucentPrim(prim)) continue;
        gl.uniform1f(gl.getUniformLocation(state.programs.mesh, "uAlphaScale"), 1);
        if (prim.meshRange) drawMeshRange(prim.meshRange);
        if (prim.tubeRanges) {
          for (const tube of prim.tubeRanges) drawMeshRange(tube);
        }
      }

      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.depthMask(false);
      for (const prim of scene.prims) {
        if (!shouldDrawPrim(prim) || !isTranslucentPrim(prim)) continue;
        gl.uniform1f(gl.getUniformLocation(state.programs.mesh, "uAlphaScale"), primAlphaScale(prim));
        if (prim.meshRange) drawMeshRange(prim.meshRange);
        if (prim.tubeRanges) {
          for (const tube of prim.tubeRanges) drawMeshRange(tube);
        }
      }
      gl.depthMask(true);
      gl.disable(gl.BLEND);

      const selected = scene.prims[state.selectedPrim];
      if (selected && shouldDrawPrim(selected)) {
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.enable(gl.POLYGON_OFFSET_FILL);
        gl.polygonOffset(-1, -1);
        gl.uniform1f(gl.getUniformLocation(state.programs.mesh, "uAlphaScale"), 1);
        gl.uniform4f(gl.getUniformLocation(state.programs.mesh, "uOverrideColor"), 0.96, 0.82, 0.25, 0.42);
        if (selected.meshRange) drawMeshRange(selected.meshRange);
        if (selected.tubeRanges) {
          for (const tube of selected.tubeRanges) drawMeshRange(tube);
        }
        gl.uniform4f(gl.getUniformLocation(state.programs.mesh, "uOverrideColor"), 0, 0, 0, -1);
        gl.disable(gl.POLYGON_OFFSET_FILL);
        gl.disable(gl.BLEND);
      }
    }

    // Draw the original BasisCurves polylines as a thin overlay only when the
    // tube generator skipped a prim (degenerate or zero-radius curve). Tubes
    // already provide visible weight for normal cases, so skipping the line
    // pass avoids redundant darker silhouettes on top of the lit cylinders.
    if (scene.lineVertexCount > 0) {
      gl.useProgram(state.programs.line);
      gl.bindVertexArray(scene.buffers.lineVao);
      gl.uniformMatrix4fv(gl.getUniformLocation(state.programs.line, "uViewProj"), false, viewProj);
      gl.lineWidth(2);
      for (const range of scene.lineRanges) {
        const prim = scene.prims[range.primIndex];
        if (!prim || !shouldDrawPrim(prim)) continue;
        if (prim.tubeRanges && prim.tubeRanges.length > 0) continue;
        gl.uniform1f(gl.getUniformLocation(state.programs.line, "uAlphaScale"), prim.sourceAlpha);
        gl.drawArrays(gl.LINE_STRIP, range.start, range.count);
      }
    }
    gl.bindVertexArray(null);
  }

  function drawPicking(scene, viewProj) {
    if (scene.meshIndexCount > 0) {
      gl.useProgram(state.programs.pickMesh);
      gl.bindVertexArray(scene.buffers.meshVao);
      gl.uniformMatrix4fv(gl.getUniformLocation(state.programs.pickMesh, "uViewProj"), false, viewProj);
      for (const range of scene.meshRanges) {
        const prim = scene.prims[range.primIndex];
        if (!prim || !shouldDrawPrim(prim)) continue;
        const color = encodePickColor(range.primIndex + 1);
        gl.uniform4f(gl.getUniformLocation(state.programs.pickMesh, "uPickColor"), color[0], color[1], color[2], 1);
        drawMeshRange(range);
      }
      // Tubes are part of the same index buffer; pick them as triangle meshes
      // so that hit areas match their visible silhouette.
      for (const range of scene.tubeRanges || []) {
        const prim = scene.prims[range.primIndex];
        if (!prim || !shouldDrawPrim(prim)) continue;
        const color = encodePickColor(range.primIndex + 1);
        gl.uniform4f(gl.getUniformLocation(state.programs.pickMesh, "uPickColor"), color[0], color[1], color[2], 1);
        drawMeshRange(range);
      }
    }

    if (scene.lineVertexCount > 0) {
      gl.useProgram(state.programs.pickLine);
      gl.bindVertexArray(scene.buffers.lineVao);
      gl.uniformMatrix4fv(gl.getUniformLocation(state.programs.pickLine, "uViewProj"), false, viewProj);
      gl.lineWidth(8);
      for (const range of scene.lineRanges) {
        const prim = scene.prims[range.primIndex];
        if (!prim || !shouldDrawPrim(prim)) continue;
        if (prim.tubeRanges && prim.tubeRanges.length > 0) continue;
        const color = encodePickColor(range.primIndex + 1);
        gl.uniform4f(gl.getUniformLocation(state.programs.pickLine, "uPickColor"), color[0], color[1], color[2], 1);
        gl.drawArrays(gl.LINE_STRIP, range.start, range.count);
      }
    }
    gl.bindVertexArray(null);
  }

  function drawMeshRange(range) {
    gl.drawElements(gl.TRIANGLES, range.count, gl.UNSIGNED_INT, range.start * 4);
  }

  function shouldDrawPrim(prim) {
    if (state.hiddenPrims.has(prim.index)) return false;
    if (prim.reviewMuted && state.surfaceMode === "hide") return false;
    return true;
  }

  function isTranslucentPrim(prim) {
    return primAlphaScale(prim) < 0.98 || prim.sourceAlpha < 0.98;
  }

  function primAlphaScale(prim) {
    if (prim.reviewMuted && state.surfaceMode === "dim") return 0.18;
    return 1;
  }

  function computeViewProjection() {
    const camera = state.camera;
    const aspect = canvas.width / Math.max(1, canvas.height);
    const basis = camera.basis;
    let eye;
    let view;
    if (basis) {
      eye = [
        camera.target[0] + camera.distance * basis.depth[0],
        camera.target[1] + camera.distance * basis.depth[1],
        camera.target[2] + camera.distance * basis.depth[2],
      ];
      view = mat4ViewFromBasis(eye, basis.right, basis.up, basis.depth);
    } else {
      const pitch = clamp(camera.pitch, -1.45, 1.45);
      const cp = Math.cos(pitch);
      eye = [
        camera.target[0] + camera.distance * cp * Math.sin(camera.yaw),
        camera.target[1] + camera.distance * cp * Math.cos(camera.yaw),
        camera.target[2] + camera.distance * Math.sin(pitch),
      ];
      view = mat4LookAt(eye, camera.target, [0, 0, 1]);
    }
    const projection = mat4Perspective(Math.PI / 4, aspect, Math.max(0.001, camera.distance / 1000), Math.max(1000, camera.distance * 20));
    return mat4Multiply(projection, view);
  }

  function initializeCameraForScene(scene) {
    fitCameraToBounds(scene.sourceViewportBounds || currentFitBounds(), false);
    applySourceViewMetadata(scene.sourceViewMetadata);
    saveCameraHome();
  }

  function fitCamera(keepAngles) {
    if (!state.scene) return;
    fitCameraToBounds(currentFitBounds(), keepAngles);
  }

  function fitCameraToBounds(bounds, keepAngles) {
    const center = [
      (bounds.min[0] + bounds.max[0]) / 2,
      (bounds.min[1] + bounds.max[1]) / 2,
      (bounds.min[2] + bounds.max[2]) / 2,
    ];
    const extents = [
      Math.max(bounds.max[0] - bounds.min[0], 0.001),
      Math.max(bounds.max[1] - bounds.min[1], 0.001),
      Math.max(bounds.max[2] - bounds.min[2], 0.001),
    ];
    const radius = Math.max(
      distance(center, bounds.min),
      distance(center, bounds.max),
      1
    );
    if (!keepAngles) {
      const suggested = suggestCameraAngles(extents);
      state.camera.yaw = suggested.yaw;
      state.camera.pitch = suggested.pitch;
      state.camera.basis = null;
    }
    state.camera.target = center;
    state.camera.distance = radius * 2.35;
    saveCameraHome();
  }

  function applySourceViewMetadata(metadata) {
    const basis = metadata && cameraBasisFromWorldRotation(metadata.worldRotation3D);
    if (!basis) return false;
    state.camera.basis = basis;
    const angles = cameraAnglesFromDirection(basis.depth);
    state.camera.yaw = angles.yaw;
    state.camera.pitch = angles.pitch;
    return true;
  }

  function saveCameraHome() {
    state.camera.home = {
      yaw: state.camera.yaw,
      pitch: state.camera.pitch,
      distance: state.camera.distance,
      target: state.camera.target.slice(),
      basis: cloneCameraBasis(state.camera.basis),
    };
  }

  function currentFitBounds() {
    if (!state.scene) return createBounds();
    const bounds = createBounds();
    for (const prim of state.scene.prims) {
      if (!hasBounds(prim.bounds) || !shouldUsePrimForFit(prim)) continue;
      expandBoundsByBounds(bounds, prim.bounds);
    }
    return hasBounds(bounds) ? bounds : state.scene.bounds;
  }

  function shouldUsePrimForFit(prim) {
    if (state.hiddenPrims.has(prim.index)) return false;
    if (prim.reviewMuted && state.surfaceMode !== "full") return false;
    return true;
  }

  function suggestCameraAngles(extents) {
    const weights = [1, 1, 1];
    const sorted = [0, 1, 2].sort((a, b) => extents[a] - extents[b]);
    const thinAxis = sorted[0];
    const nextAxis = sorted[1];
    const thinRatio = extents[thinAxis] / Math.max(extents[nextAxis], 0.001);
    if (thinRatio < 0.7) {
      weights[thinAxis] = clamp(thinRatio, 0.18, 0.6);
    }
    const length = Math.hypot(weights[0], weights[1], weights[2]) || 1;
    const direction = [weights[0] / length, weights[1] / length, weights[2] / length];
    return {
      yaw: Math.atan2(direction[0], direction[1]),
      pitch: Math.asin(clamp(direction[2], -0.92, 0.92)),
    };
  }

  function cameraDirectionFromAngles(yaw, pitch) {
    const clampedPitch = clamp(pitch, -1.45, 1.45);
    const cp = Math.cos(clampedPitch);
    return normalize([
      cp * Math.sin(yaw),
      cp * Math.cos(yaw),
      Math.sin(clampedPitch),
    ]);
  }

  function cameraAnglesFromDirection(direction) {
    const normalized = normalize(direction);
    return {
      yaw: Math.atan2(normalized[0], normalized[1]),
      pitch: Math.asin(clamp(normalized[2], -0.999, 0.999)),
    };
  }

  function cameraBasisFromWorldRotation(rotation) {
    if (!window.Desmos2UsdCamera) return null;
    return window.Desmos2UsdCamera.cameraBasisFromWorldRotation(rotation);
  }

  function cloneCameraBasis(basis) {
    if (!basis) return null;
    return {
      right: basis.right.slice(),
      up: basis.up.slice(),
      depth: basis.depth.slice(),
    };
  }

  function releaseCameraBasisToAngles() {
    if (!state.camera.basis) return;
    const angles = cameraAnglesFromDirection(state.camera.basis.depth);
    state.camera.yaw = angles.yaw;
    state.camera.pitch = angles.pitch;
    state.camera.basis = null;
  }

  function resetCamera() {
    if (!state.camera.home) return;
    state.camera.yaw = state.camera.home.yaw;
    state.camera.pitch = state.camera.home.pitch;
    state.camera.distance = state.camera.home.distance;
    state.camera.target = state.camera.home.target.slice();
    state.camera.basis = cloneCameraBasis(state.camera.home.basis);
  }

  function onWheel(event) {
    if (!state.scene) return;
    event.preventDefault();
    const scale = Math.exp(event.deltaY * 0.001);
    state.camera.distance = clamp(state.camera.distance * scale, 0.01, 1e8);
  }

  function onPointerDown(event) {
    canvas.setPointerCapture(event.pointerId);
    state.pointers.set(event.pointerId, pointerFromEvent(event));
    state.drag = {
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      lastPinchDistance: null,
      lastCenter: null,
      mode: event.button === 2 || event.shiftKey ? "pan" : "orbit",
    };
  }

  function onPointerMove(event) {
    if (!state.pointers.has(event.pointerId)) return;
    state.pointers.set(event.pointerId, pointerFromEvent(event));
    if (!state.drag || !state.scene) return;

    const pointers = Array.from(state.pointers.values());
    if (pointers.length >= 2) {
      const a = pointers[0];
      const b = pointers[1];
      const center = [(a.x + b.x) / 2, (a.y + b.y) / 2];
      const pinchDistance = Math.hypot(a.x - b.x, a.y - b.y);
      if (state.drag.lastPinchDistance) {
        state.camera.distance = clamp(state.camera.distance * (state.drag.lastPinchDistance / Math.max(1, pinchDistance)), 0.01, 1e8);
      }
      if (state.drag.lastCenter) {
        panCamera(center[0] - state.drag.lastCenter[0], center[1] - state.drag.lastCenter[1]);
      }
      state.drag.lastPinchDistance = pinchDistance;
      state.drag.lastCenter = center;
      return;
    }

    const dx = event.clientX - state.drag.lastX;
    const dy = event.clientY - state.drag.lastY;
    if (state.drag.mode === "pan" || (event.buttons & 2)) {
      panCamera(dx, dy);
    } else {
      releaseCameraBasisToAngles();
      state.camera.yaw -= dx * 0.006;
      state.camera.pitch = clamp(state.camera.pitch + dy * 0.006, -1.45, 1.45);
    }
    state.drag.lastX = event.clientX;
    state.drag.lastY = event.clientY;
  }

  function onPointerUp(event) {
    state.pointers.delete(event.pointerId);
    if (state.drag && Math.hypot(event.clientX - state.drag.startX, event.clientY - state.drag.startY) < 5) {
      pickAt(event.clientX, event.clientY);
    }
    if (state.pointers.size === 0) state.drag = null;
  }

  function panCamera(dx, dy) {
    const camera = state.camera;
    const basis = camera.basis;
    const eyeDir = basis ? basis.depth : cameraDirectionFromAngles(camera.yaw, camera.pitch);
    const right = basis ? basis.right : normalize(cross(eyeDir, [0, 0, 1]));
    const up = basis ? basis.up : normalize(cross(right, eyeDir));
    const scale = camera.distance * 0.0016;
    camera.target[0] += (-right[0] * dx + up[0] * dy) * scale;
    camera.target[1] += (-right[1] * dx + up[1] * dy) * scale;
    camera.target[2] += (-right[2] * dx + up[2] * dy) * scale;
  }

  function pointerFromEvent(event) {
    return { x: event.clientX, y: event.clientY };
  }

  function pickAt(clientX, clientY) {
    if (!state.scene) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((clientX - rect.left) * state.dpr);
    const y = Math.floor((rect.bottom - clientY) * state.dpr);
    drawScene(true);
    const pixel = new Uint8Array(4);
    gl.bindFramebuffer(gl.FRAMEBUFFER, state.pickFramebuffer);
    gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    const id = pixel[0] + pixel[1] * 256 + pixel[2] * 65536;
    selectPrim(id > 0 && id <= state.scene.prims.length ? id - 1 : -1);
  }

  function selectPrim(index) {
    state.selectedPrim = index;
    updateSelection();
    renderPrimList();
  }

  function focusSelectedPrim() {
    const prim = state.scene && state.scene.prims[state.selectedPrim];
    if (!prim || !hasBounds(prim.bounds)) return;
    fitCameraToBounds(prim.bounds, true);
  }

  function toggleSelectedPrimVisibility() {
    const prim = state.scene && state.scene.prims[state.selectedPrim];
    if (!prim) return;
    if (state.hiddenPrims.has(prim.index)) {
      state.hiddenPrims.delete(prim.index);
    } else {
      state.hiddenPrims.add(prim.index);
    }
    updateSummary();
    updateSelection();
    renderPrimList();
  }

  function cycleSurfaceMode() {
    if (state.surfaceMode === "dim") {
      state.surfaceMode = "hide";
    } else if (state.surfaceMode === "hide") {
      state.surfaceMode = "full";
    } else {
      state.surfaceMode = "dim";
    }
    updateSurfaceModeButton();
    updateSummary();
    updateSelection();
    renderPrimList();
  }

  function updateSurfaceModeButton() {
    const labels = {
      dim: "Panels: Dim",
      hide: "Panels: Hide",
      full: "Panels: Full",
    };
    panelModeButton.textContent = labels[state.surfaceMode] || labels.dim;
    panelModeButton.disabled = !state.scene || state.scene.stats.reviewMutedCount === 0;
  }

  function updateSummary() {
    if (!state.scene) {
      sceneSummary.innerHTML = "<dt>File</dt><dd>-</dd><dt>Prims</dt><dd>-</dd><dt>Faces</dt><dd>-</dd><dt>Points</dt><dd>-</dd>";
      return;
    }
    const scene = state.scene;
    const layerTitle = scene.layer["desmos:title"] || "";
    sceneSummary.innerHTML = [
      ["File", escapeHtml(scene.fileName)],
      ["Title", escapeHtml(layerTitle || "-")],
      ["Prims", scene.stats.primCount.toLocaleString()],
      ["Meshes", scene.stats.meshPrims.toLocaleString()],
      ["Curves", scene.stats.curvePrims.toLocaleString()],
      ["Dimmed", scene.stats.reviewMutedCount.toLocaleString()],
      ["Hidden", state.hiddenPrims.size.toLocaleString()],
      ["Faces", scene.stats.faceCount.toLocaleString()],
      ["Points", scene.stats.pointCount.toLocaleString()],
    ].map(([key, value]) => `<dt>${key}</dt><dd>${value}</dd>`).join("");
  }

  function updateSelection() {
    const scene = state.scene;
    const prim = scene && scene.prims[state.selectedPrim];
    if (!prim) {
      selectionPanel.textContent = "Click a prim or choose one below.";
      return;
    }
    const metadata = prim.metadata;
    const hidden = state.hiddenPrims.has(prim.index);
    const reviewState = prim.reviewMuted ? `${state.surfaceMode === "full" ? "full" : state.surfaceMode} (${prim.reviewReason})` : "-";
    const rows = [
      ["Name", prim.name],
      ["Type", prim.type],
      ["Expr", metadata["desmos:exprId"] || "-"],
      ["Order", metadata["desmos:order"] ?? "-"],
      ["Kind", metadata["desmos:kind"] || "-"],
      ["Color", metadata["desmos:color"] || prim.colorHex],
      ["Review", reviewState],
      ["Visible", hidden ? "No" : "Yes"],
      ["Faces", prim.faceCount.toLocaleString()],
      ["Points", prim.pointCount.toLocaleString()],
      ["Latex", metadata["desmos:latex"] || "-"],
      ["Bounds", metadata["desmos:constraints"] || "-"],
    ];
    selectionPanel.innerHTML = `
      <div class="selection-title"><span class="swatch" style="background:${prim.colorHex}"></span>${escapeHtml(prim.name)}</div>
      <div class="selection-actions">
        <button type="button" data-action="focus">Focus</button>
        <button type="button" data-action="visibility">${hidden ? "Show" : "Hide"}</button>
      </div>
      <dl class="metadata-grid">
        ${rows.map(([key, value]) => `<dt>${key}</dt><dd>${escapeHtml(String(value))}</dd>`).join("")}
      </dl>
    `;
    selectionPanel.querySelector('[data-action="focus"]').addEventListener("click", focusSelectedPrim);
    selectionPanel.querySelector('[data-action="visibility"]').addEventListener("click", toggleSelectedPrimVisibility);
  }

  function renderPrimList() {
    primList.innerHTML = "";
    if (!state.scene) return;
    const query = primFilter.value.trim().toLowerCase();
    const fragment = document.createDocumentFragment();
    for (const prim of state.scene.prims) {
      const label = `${prim.name} ${prim.type} ${prim.metadata["desmos:exprId"] || ""} ${prim.metadata["desmos:kind"] || ""} ${prim.metadata["desmos:latex"] || ""}`;
      if (query && !label.toLowerCase().includes(query)) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = `prim-row${state.hiddenPrims.has(prim.index) ? " hidden" : ""}${prim.reviewMuted ? " review-muted" : ""}`;
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(prim.index === state.selectedPrim));
      button.addEventListener("click", () => selectPrim(prim.index));
      const tags = [
        prim.reviewMuted ? state.surfaceMode : "",
        state.hiddenPrims.has(prim.index) ? "hidden" : "",
      ].filter(Boolean);
      button.innerHTML = `
        <span class="swatch" style="background:${prim.colorHex}"></span>
        <span class="name">${escapeHtml(prim.name)}</span>
        <span class="count">${escapeHtml(tags.length ? tags.join(" ") : (prim.faceCount ? prim.faceCount.toLocaleString() + " faces" : prim.pointCount.toLocaleString() + " pts"))}</span>
      `;
      fragment.appendChild(button);
    }
    primList.appendChild(fragment);
  }

  function ensurePickFramebuffer() {
    if (state.pickFramebuffer && state.pickSize[0] === canvas.width && state.pickSize[1] === canvas.height) {
      return state.pickFramebuffer;
    }
    if (state.pickFramebuffer) {
      gl.deleteFramebuffer(state.pickFramebuffer);
      gl.deleteTexture(state.pickTexture);
      gl.deleteRenderbuffer(state.pickDepth);
    }
    const framebuffer = gl.createFramebuffer();
    const texture = gl.createTexture();
    const depth = gl.createRenderbuffer();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, canvas.width, canvas.height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.bindRenderbuffer(gl.RENDERBUFFER, depth);
    gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, canvas.width, canvas.height);
    gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, depth);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    state.pickFramebuffer = framebuffer;
    state.pickTexture = texture;
    state.pickDepth = depth;
    state.pickSize = [canvas.width, canvas.height];
    return framebuffer;
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const nextDpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(rect.width * nextDpr));
    const height = Math.max(1, Math.floor(rect.height * nextDpr));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      state.dpr = nextDpr;
    }
  }

  function disposeScene() {
    if (!state.scene) return;
    const buffers = state.scene.buffers;
    gl.deleteVertexArray(buffers.meshVao);
    gl.deleteBuffer(buffers.positionBuffer);
    gl.deleteBuffer(buffers.colorBuffer);
    gl.deleteBuffer(buffers.normalBuffer);
    gl.deleteBuffer(buffers.indexBuffer);
    gl.deleteVertexArray(buffers.lineVao);
    gl.deleteBuffer(buffers.linePositionBuffer);
    gl.deleteBuffer(buffers.lineColorBuffer);
    state.scene = null;
  }

  function parseColor(value) {
    const fallback = [103, 183, 220];
    if (typeof value !== "string") return fallback;
    const match = value.trim().match(/^#?([0-9a-fA-F]{6})$/);
    if (!match) return fallback;
    const hex = match[1];
    return [
      Number.parseInt(hex.slice(0, 2), 16),
      Number.parseInt(hex.slice(2, 4), 16),
      Number.parseInt(hex.slice(4, 6), 16),
    ];
  }

  function rgbToHex(color) {
    return `#${color.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
  }

  function encodePickColor(id) {
    return [
      (id & 255) / 255,
      ((id >> 8) & 255) / 255,
      ((id >> 16) & 255) / 255,
    ];
  }

  function parseSourceViewportBounds(layer) {
    const raw = layer && layer["desmos:viewportBounds"];
    if (typeof raw !== "string" || !raw) return null;
    try {
      const parsed = JSON.parse(raw);
      const axes = ["x", "y", "z"];
      const min = [];
      const max = [];
      for (const axis of axes) {
        const bounds = parsed[axis];
        if (!Array.isArray(bounds) || bounds.length < 2) return null;
        const low = Number(bounds[0]);
        const high = Number(bounds[1]);
        if (!Number.isFinite(low) || !Number.isFinite(high)) return null;
        min.push(low);
        max.push(high);
      }
      return { min, max };
    } catch (_error) {
      return null;
    }
  }

  function parseSourceViewMetadata(layer) {
    if (!layer) return null;
    const metadata = {};
    const rotation = parseSourceFloatSequence(layer["desmos:worldRotation3D"], 9);
    if (rotation) metadata.worldRotation3D = rotation;
    const axis = parseSourceFloatSequence(layer["desmos:axis3D"], 3);
    if (axis) metadata.axis3D = axis;
    for (const [sourceKey, targetKey] of [
      ["desmos:threeDMode", "threeDMode"],
      ["desmos:showPlane3D", "showPlane3D"],
      ["desmos:degreeMode", "degreeMode"],
    ]) {
      const parsed = parseSourceBoolean(layer[sourceKey]);
      if (parsed !== null) metadata[targetKey] = parsed;
    }
    return Object.keys(metadata).length ? metadata : null;
  }

  function parseSourceFloatSequence(raw, expectedLength) {
    let value = raw;
    if (typeof value === "string") {
      try {
        value = JSON.parse(value);
      } catch (_error) {
        return null;
      }
    }
    if (!Array.isArray(value) || value.length !== expectedLength) return null;
    const parsed = value.map((item) => Number(item));
    if (parsed.some((item) => !Number.isFinite(item))) return null;
    return parsed;
  }

  function parseSourceBoolean(raw) {
    if (typeof raw === "boolean") return raw;
    if (typeof raw !== "string") return null;
    const normalized = raw.trim().toLowerCase();
    if (normalized === "true") return true;
    if (normalized === "false") return false;
    return null;
  }

  function createBounds() {
    return { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] };
  }

  function hasBounds(bounds) {
    return Boolean(bounds) && Number.isFinite(bounds.min[0]) && Number.isFinite(bounds.max[0]);
  }

  function expandBounds(bounds, point) {
    for (let i = 0; i < 3; i += 1) {
      bounds.min[i] = Math.min(bounds.min[i], point[i]);
      bounds.max[i] = Math.max(bounds.max[i], point[i]);
    }
  }

  function expandBoundsByBounds(bounds, source) {
    if (!hasBounds(source)) return;
    expandBounds(bounds, source.min);
    expandBounds(bounds, source.max);
  }

  function annotateReviewSurfaces(prims, sceneBounds) {
    const sceneDiagonal = Math.max(boundsDiagonal(sceneBounds), 1);
    for (const prim of prims) {
      if (!hasBounds(prim.bounds)) continue;
      prim.extents = boundsExtents(prim.bounds);
      prim.diagonal = boundsDiagonal(prim.bounds);
      if (isLargeNeutralUnderboundedSurface(prim, sceneDiagonal)) {
        prim.reviewMuted = true;
        prim.reviewReason = "large underbounded neutral surface";
      }
    }
  }

  function isLargeNeutralUnderboundedSurface(prim, sceneDiagonal) {
    if (prim.type !== "Mesh") return false;
    if (prim.metadata["desmos:kind"] !== "explicit_surface") return false;
    if (!isNeutralColor(prim.color)) return false;
    if (!hasMissingDomainConstraint(prim)) return false;
    const largest = Math.max(...prim.extents);
    const smallest = Math.min(...prim.extents);
    const flatRatio = largest > 0 ? smallest / largest : 1;
    return flatRatio < 0.02 && prim.diagonal >= sceneDiagonal * 0.45;
  }

  function hasMissingDomainConstraint(prim) {
    const latex = String(prim.metadata["desmos:latex"] || "");
    const constraints = String(prim.metadata["desmos:constraints"] || "");
    const match = latex.match(/^\s*([xyz])\s*=/);
    if (!match) return false;
    const solvedAxis = match[1];
    const domainAxes = ["x", "y", "z"].filter((axis) => axis !== solvedAxis);
    return domainAxes.some((axis) => !mentionsAxis(constraints, axis));
  }

  function mentionsAxis(text, axis) {
    const pattern = new RegExp(`(^|[^A-Za-z0-9_\\\\])${axis}([^A-Za-z0-9_]|$)`);
    return pattern.test(text);
  }

  function isNeutralColor(color) {
    if (!Array.isArray(color) || color.length < 3) return false;
    const low = Math.min(color[0], color[1], color[2]);
    const high = Math.max(color[0], color[1], color[2]);
    const mean = (color[0] + color[1] + color[2]) / 3;
    return high - low <= 18 && mean >= 70 && mean <= 220;
  }

  function boundsExtents(bounds) {
    return [
      Math.max(bounds.max[0] - bounds.min[0], 0),
      Math.max(bounds.max[1] - bounds.min[1], 0),
      Math.max(bounds.max[2] - bounds.min[2], 0),
    ];
  }

  function boundsDiagonal(bounds) {
    const extents = boundsExtents(bounds);
    return Math.hypot(extents[0], extents[1], extents[2]);
  }

  function mat4Perspective(fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2);
    const nf = 1 / (near - far);
    return new Float32Array([
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) * nf, -1,
      0, 0, 2 * far * near * nf, 0,
    ]);
  }

  function mat4LookAt(eye, target, up) {
    const z = normalize([eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]]);
    const x = normalize(cross(up, z));
    const y = cross(z, x);
    return new Float32Array([
      x[0], y[0], z[0], 0,
      x[1], y[1], z[1], 0,
      x[2], y[2], z[2], 0,
      -dot(x, eye), -dot(y, eye), -dot(z, eye), 1,
    ]);
  }

  function mat4ViewFromBasis(eye, right, up, depth) {
    return new Float32Array([
      right[0], up[0], depth[0], 0,
      right[1], up[1], depth[1], 0,
      right[2], up[2], depth[2], 0,
      -dot(right, eye), -dot(up, eye), -dot(depth, eye), 1,
    ]);
  }

  function mat4Multiply(a, b) {
    const out = new Float32Array(16);
    for (let col = 0; col < 4; col += 1) {
      for (let row = 0; row < 4; row += 1) {
        out[col * 4 + row] =
          a[0 * 4 + row] * b[col * 4 + 0] +
          a[1 * 4 + row] * b[col * 4 + 1] +
          a[2 * 4 + row] * b[col * 4 + 2] +
          a[3 * 4 + row] * b[col * 4 + 3];
      }
    }
    return out;
  }

  function cross(a, b) {
    return [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0],
    ];
  }

  function dot(a, b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  }

  function normalize(v) {
    const length = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / length, v[1] / length, v[2] / length];
  }

  function distance(a, b) {
    return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));
  }

  function setStatus(message) {
    statusText.textContent = message;
  }

  function nextFrame() {
    return new Promise((resolve) => requestAnimationFrame(resolve));
  }
}());
