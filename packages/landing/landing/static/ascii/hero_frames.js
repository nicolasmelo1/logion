// SPDX-License-Identifier: MIT
// Decode frames for the hero "boot" sequence. Each frame is a square
// ASCII silhouette of the Zeus bust, progressively resolving from noise
// to the final figure. Consumed by app.js for the intro cycle.
// No network assets; pure string data.
(function (global) {
  "use strict";

  // Final silhouette: dense Greek/symbol glyphs marking the figure.
  var FINAL = [
    "          ░▒▓████▓▒░          ",
    "       ░▒▓██████████▓▒░       ",
    "     ░▒▓██████████████▓▒░     ",
    "    ▒▓████████████████████▒   ",
    "   ▓██████░░░░░░░░░░██████▓   ",
    "  ▓█████░    Φ    Φ    █████▓ ",
    "  █████░   ███    ███   █████ ",
    "  █████░   ███    ███   █████ ",
    "  █████░    Ψ    Ψ    █████   ",
    "  █████░     ▓▓▓▓▓▓     █████ ",
    "  █████░    ▓▓▓▓▓▓▓▓    █████ ",
    "   █████░  ▓▓ ░░░░ ▓▓  █████  ",
    "   ▓█████ ▓▓░▓▓▓▓▓▓░▓▓ █████▓ ",
    "    █████▓▓▓▓▓▓▓▓▓▓▓▓▓▓█████  ",
    "    ▓████▓▓▓▓▓▓▓▓▓▓▓▓▓▓████▓  ",
    "     ████▓▓▓▓▓▓▓▓▓▓▓▓▓▓████   ",
    "      ███▓▓▓▓▓▓▓▓▓▓▓▓▓▓███    ",
    "       ▓█▓▓▓▓▓▓▓▓▓▓▓▓▓█▓      ",
    "         ▓▓▓▓▓▓▓▓▓▓▓▓▓        ",
    "      ░▓██████████████▓░      ",
    "  ░▒▓█████████████████████▓▒░ ",
    "▒▓██████████████████████████▓▒",
    "████████████████████████████████",
    "████████████████████████████████",
  ];

  var NOISE_CHARS = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ ·∙+▪░▒▓█";

  function noiseChar(seed) {
    // deterministic pseudo-random pick
    var v = Math.sin(seed * 12.9898) * 43758.5453;
    var i = Math.floor((v - Math.floor(v)) * NOISE_CHARS.length);
    return NOISE_CHARS[i];
  }

  // Build a partially-resolved frame. resolution in [0,1]; 0 = full noise,
  // 1 = final silhouette.
  function buildFrame(resolution, seedBase) {
    var width = 0;
    for (var i = 0; i < FINAL.length; i++) {
      if (FINAL[i].length > width) width = FINAL[i].length;
    }
    var out = [];
    for (var y = 0; y < FINAL.length; y++) {
      var row = "";
      var src = FINAL[y];
      for (var x = 0; x < width; x++) {
        var ch = x < src.length ? src[x] : " ";
        var solid = ch !== " ";
        var rand = Math.sin((x * 7 + y * 13 + seedBase) * 0.5) * 0.5 + 0.5;
        if (rand < resolution) {
          row += ch;
        } else if (solid) {
          row += noiseChar(seedBase + x * 31 + y * 17);
        } else {
          // sparse background flicker
          row += rand > 0.97 ? noiseChar(seedBase + x + y) : " ";
        }
      }
      out.push(row);
    }
    return out.join("\n");
  }

  var FRAMES = [
    buildFrame(0.05, 1),
    buildFrame(0.18, 2),
    buildFrame(0.32, 3),
    buildFrame(0.48, 4),
    buildFrame(0.64, 5),
    buildFrame(0.78, 6),
    buildFrame(0.9, 7),
    buildFrame(1.0, 8),
  ];

  global.LOGION_HERO_FRAMES = FRAMES;
  global.LOGION_HERO_SILHOUETTE = FINAL.join("\n");
})(typeof window !== "undefined" ? window : globalThis);
