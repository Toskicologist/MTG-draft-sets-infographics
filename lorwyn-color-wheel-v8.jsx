/**
 * Lorwyn Eclipsed Draft Archetypes - Color Wheel Visualization
 * v8 React - Port of Python de-overlap algorithm
 *
 * Key features ported from Python version:
 * - Iterative collision detection pushes overlapping labels apart
 * - Labels start at edge midpoints with outward normal offset
 * - Smart color rules for background/text readability
 * - Bounding box overlap detection
 *
 * v8 Python - Working de-overlap algorithm
 * v7 and earlier - Various failed attempts at manual positioning
 */

import React, { useMemo } from 'react';

// ---------------- Configuration ----------------
const CONFIG = {
  width: 700,
  height: 700,
  cx: 350,
  cy: 330,
  radius: 180,
  nodeRadius: 30,
  edgeWidth: 5,
  boxW: 95,
  boxH: 58,
  fontSize: 12,
  iterMax: 240,
  pushStep: 6,
};

// ---------------- Base colors ----------------
const baseHex = {
  W: "#FFFFFF",
  U: "#3366FF",
  B: "#000000",
  R: "#FF3333",
  G: "#2ECC40",
};

// ---------------- Lorwyn Eclipsed Archetypes ----------------
const labels = {
  WU: { text: "*Merfolk", sub: "Tap triggers" },
  UB: { text: "Flash", sub: "Trickery" },
  BR: { text: "*Goblins", sub: "Blight & sacrifice" },
  RG: { text: "Vivid", sub: "Beatdown" },
  GW: { text: "*Kithkin", sub: "Go-wide tokens" },
  WB: { text: "Persist", sub: "Recursion" },
  UR: { text: "*Elementals", sub: "Big spells 4+" },
  BG: { text: "*Elves", sub: "Graveyard value" },
  RW: { text: "Giants", sub: "Aggro" },
  GU: { text: "Vivid", sub: "Ramp" },
};

// ---------------- Color helpers ----------------
const hexToRgb = (h) => {
  const hex = h.replace('#', '');
  return [
    parseInt(hex.substring(0, 2), 16),
    parseInt(hex.substring(2, 4), 16),
    parseInt(hex.substring(4, 6), 16),
  ];
};

const rgbToHex = (r, g, b) =>
  '#' + [r, g, b].map(x => Math.round(x).toString(16).padStart(2, '0')).join('');

const darken = (h, amt = 0.4) => {
  const [r, g, b] = hexToRgb(h);
  return rgbToHex(r * (1 - amt), g * (1 - amt), b * (1 - amt));
};

const blend = (u, v) => {
  const [r1, g1, b1] = hexToRgb(baseHex[u]);
  const [r2, g2, b2] = hexToRgb(baseHex[v]);
  return rgbToHex((r1 + r2) / 2, (g1 + g2) / 2, (b1 + b2) / 2);
};

const relLum = (h) => {
  const [r, g, b] = hexToRgb(h).map(x => x / 255);
  const f = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};

const contrastRatio = (bg, fg) => {
  const [L1, L2] = [relLum(bg), relLum(fg)].sort((a, b) => b - a);
  return (L1 + 0.05) / (L2 + 0.05);
};

const getLabelColors = (u, v) => {
  let bg, fg;
  if (u === 'B' || v === 'B') {
    bg = '#000000';
    const partner = u === 'B' ? v : u;
    fg = partner === 'W' ? '#FFFFFF' : baseHex[partner];
  } else if (u === 'W' || v === 'W') {
    const partner = u === 'W' ? v : u;
    bg = darken(baseHex[partner], 0.4);
    fg = '#FFFFFF';
  } else {
    bg = darken(baseHex[u], 0.4);
    fg = baseHex[v];
    if (contrastRatio(bg, fg) < 4.5) {
      const [r, g, b] = hexToRgb(fg);
      fg = rgbToHex(Math.min(r + 140, 255), Math.min(g + 140, 255), Math.min(b + 140, 255));
    }
  }
  return { bg, fg };
};

// ---------------- Geometry ----------------
const colorOrder = ['W', 'U', 'B', 'R', 'G'];

const getNodePos = (index) => {
  const angle = (index * 72 - 90) * (Math.PI / 180);
  return {
    x: CONFIG.cx + CONFIG.radius * Math.cos(angle),
    y: CONFIG.cy + CONFIG.radius * Math.sin(angle),
  };
};

const nodePositions = colorOrder.map((_, i) => getNodePos(i));

// All edges (pairs)
const edges = Object.keys(labels).map(pair => ({
  u: pair[0],
  v: pair[1],
  uIdx: colorOrder.indexOf(pair[0]),
  vIdx: colorOrder.indexOf(pair[1]),
}));

// Calculate visible midpoint and normal
const getEdgeGeometry = (uIdx, vIdx) => {
  const p1 = nodePositions[uIdx];
  const p2 = nodePositions[vIdx];
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const L = Math.hypot(dx, dy);
  const ux = dx / L;
  const uy = dy / L;
  
  // Midpoint of visible edge (excluding node radii)
  const x = (p1.x + ux * CONFIG.nodeRadius + p2.x - ux * CONFIG.nodeRadius) / 2;
  const y = (p1.y + uy * CONFIG.nodeRadius + p2.y - uy * CONFIG.nodeRadius) / 2;
  
  // Tangent and normal
  const tx = ux, ty = uy;
  const nx = -uy, ny = ux;
  
  return { x, y, tx, ty, nx, ny };
};

// Bounding box
const getBbox = (cx, cy) => ({
  x1: cx - CONFIG.boxW / 2,
  x2: cx + CONFIG.boxW / 2,
  y1: cy - CONFIG.boxH / 2,
  y2: cy + CONFIG.boxH / 2,
});

// Overlap detection
const isOverlap = (b1, b2, margin = 2) => {
  return !(b1.x2 + margin < b2.x1 || b2.x2 + margin < b1.x1 ||
           b1.y2 + margin < b2.y1 || b2.y2 + margin < b1.y1);
};

// ---------------- De-overlap Algorithm ----------------
const computeLabelPositions = () => {
  // Initial placement
  const groups = edges.map(edge => {
    const { x, y, tx, ty, nx, ny } = getEdgeGeometry(edge.uIdx, edge.vIdx);
    
    // Push outward from center
    const sgn = (x - CONFIG.cx) * nx + (y - CONFIG.cy) * ny > 0 ? 1 : -1;
    const off = sgn * 15;
    const tshift = edge.u < edge.v ? 3 : -3;
    
    const cx = x + nx * off + tx * tshift;
    const cy = y + ny * off + ty * tshift;
    
    return {
      ...edge,
      cx,
      cy,
      bbox: getBbox(cx, cy),
    };
  });

  // Iterative de-overlap
  for (let iter = 0; iter < CONFIG.iterMax; iter++) {
    let moved = false;
    for (let i = 0; i < groups.length; i++) {
      for (let j = i + 1; j < groups.length; j++) {
        if (isOverlap(groups[i].bbox, groups[j].bbox)) {
          const dx = groups[i].cx - groups[j].cx;
          const dy = groups[i].cy - groups[j].cy;
          const L = Math.hypot(dx, dy) + 0.001;
          
          groups[i].cx += (dx / L) * CONFIG.pushStep;
          groups[i].cy += (dy / L) * CONFIG.pushStep;
          groups[j].cx -= (dx / L) * CONFIG.pushStep;
          groups[j].cy -= (dy / L) * CONFIG.pushStep;
          
          groups[i].bbox = getBbox(groups[i].cx, groups[i].cy);
          groups[j].bbox = getBbox(groups[j].cx, groups[j].cy);
          moved = true;
        }
      }
    }
    if (!moved) break;
  }

  return groups;
};

// Pre-compute positions (runs once)
const labelPositions = computeLabelPositions();

// ---------------- Components ----------------
const ColorNode = ({ color, index }) => {
  const pos = nodePositions[index];
  return (
    <g>
      {/* Glow */}
      <circle cx={pos.x} cy={pos.y} r={CONFIG.nodeRadius + 8} fill={baseHex[color]} opacity={0.25} />
      {/* Main circle */}
      <circle
        cx={pos.x}
        cy={pos.y}
        r={CONFIG.nodeRadius}
        fill={baseHex[color]}
        stroke="#000000"
        strokeWidth={3}
      />
      {/* Letter */}
      <text
        x={pos.x}
        y={pos.y + 7}
        textAnchor="middle"
        fontSize={CONFIG.nodeRadius * 1.2}
        fontWeight="bold"
        fill={color === 'W' ? '#000000' : '#FFFFFF'}
      >
        {color}
      </text>
    </g>
  );
};

const EdgeLine = ({ edge }) => {
  const p1 = nodePositions[edge.uIdx];
  const p2 = nodePositions[edge.vIdx];
  return (
    <line
      x1={p1.x}
      y1={p1.y}
      x2={p2.x}
      y2={p2.y}
      stroke={blend(edge.u, edge.v)}
      strokeWidth={CONFIG.edgeWidth}
    />
  );
};

const LabelBox = ({ group }) => {
  const code = group.u + group.v;
  const labelData = labels[code] || labels[group.v + group.u];
  const { bg, fg } = getLabelColors(group.u, group.v);
  const edgeColor = blend(group.u, group.v);
  
  return (
    <g>
      <rect
        x={group.bbox.x1}
        y={group.bbox.y1}
        width={CONFIG.boxW}
        height={CONFIG.boxH}
        rx={6}
        fill={bg}
        stroke={edgeColor}
        strokeWidth={2}
      />
      <text
        x={group.cx}
        y={group.cy - 12}
        textAnchor="middle"
        fontSize={CONFIG.fontSize}
        fontWeight="bold"
        fill={fg}
      >
        {code}
      </text>
      <text
        x={group.cx}
        y={group.cy + 3}
        textAnchor="middle"
        fontSize={CONFIG.fontSize - 1}
        fill={fg}
      >
        {labelData.text}
      </text>
      <text
        x={group.cx}
        y={group.cy + 17}
        textAnchor="middle"
        fontSize={CONFIG.fontSize - 2}
        fill={fg}
        opacity={0.85}
      >
        {labelData.sub}
      </text>
    </g>
  );
};

// ---------------- Main Component ----------------
export default function LorwynColorWheel() {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#FFFFFF',
      padding: '24px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '16px' }}>
        <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#111827', margin: '0 0 4px 0' }}>
          Lorwyn Eclipsed
        </h1>
        <p style={{ fontSize: '0.95rem', color: '#6B7280', margin: 0 }}>
          Draft Archetypes Color Wheel (v8 React)
        </p>
      </div>

      {/* SVG Diagram */}
      <svg width={CONFIG.width} height={CONFIG.height} style={{ maxWidth: '100%' }}>
        {/* Edges first (behind nodes) */}
        {edges.map((edge, i) => (
          <EdgeLine key={`edge-${i}`} edge={edge} />
        ))}
        
        {/* Nodes */}
        {colorOrder.map((color, i) => (
          <ColorNode key={color} color={color} index={i} />
        ))}
        
        {/* Labels (on top) */}
        {labelPositions.map((group, i) => (
          <LabelBox key={`label-${i}`} group={group} />
        ))}
      </svg>

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: '20px',
        flexWrap: 'wrap',
        justifyContent: 'center',
        marginTop: '16px',
        padding: '12px 24px',
        backgroundColor: '#F9FAFB',
        borderRadius: '8px',
        border: '1px solid #E5E7EB',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.85rem', color: '#4B5563' }}>* = Typal (gold signpost uncommon)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.85rem', color: '#4B5563' }}>No * = Mechanical (hybrid only)</span>
        </div>
      </div>

      {/* Footer */}
      <p style={{ fontSize: '0.75rem', color: '#9CA3AF', marginTop: '12px', textAlign: 'center' }}>
        Prereleases Jan 16–22, 2026 · Faeries & Giants supported at higher rarities
      </p>
    </div>
  );
}
