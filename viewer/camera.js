(function (root) {
  "use strict";

  function cameraBasisFromWorldRotation(rotation) {
    if (!Array.isArray(rotation) || rotation.length !== 9) return null;
    const rows = [
      rotation.slice(0, 3),
      rotation.slice(3, 6),
      rotation.slice(6, 9),
    ];
    if (rows.some((row) => row.some((value) => !Number.isFinite(value)) || Math.hypot(row[0], row[1], row[2]) < 1e-6)) {
      return null;
    }

    const right = normalize(rows[0]);
    const up = normalize(rows[1]);
    const depth = normalize(rows[2]);
    if (Math.abs(dot(cross(right, up), depth)) < 0.4) return null;
    return { right, up, depth };
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

  const api = { cameraBasisFromWorldRotation };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.Desmos2UsdCamera = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
