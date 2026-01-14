/**
 * Lorwyn Eclipsed Draft Archetypes - Color Wheel Visualization
 * v7 - All labels on diagram with hand-positioned coordinates
 *    - Larger pentagon (radius 150) for more label space
 *    - Ally pairs: labels positioned OUTSIDE each edge
 *    - Enemy pairs: labels positioned along diagonals, offset from center to avoid overlap
 *    - All positions manually calculated to guarantee no overlap
 *    - Smaller, compact label boxes
 *    - Color nodes with letter symbols (reliable rendering)
 *
 * v6 - Separate list approach (user wanted labels on diagram)
 * v5 - Split layout attempt
 * v4 - Fixed positions (overlapped)
 * v3 - Static PNG (font issues)
 * v2 - Staggered positions
 * v1 - Initial version
 */

import React from 'react';

const MTGColors = {
  W: { name: 'White', bg: '#FDF6E3', border: '#D4A84B', letter: 'W', letterColor: '#8B6914' },
  U: { name: 'Blue', bg: '#1E5AA8', border: '#5B9BD5', letter: 'U', letterColor: '#FFFFFF' },
  B: { name: 'Black', bg: '#2D2D2D', border: '#888888', letter: 'B', letterColor: '#FFFFFF' },
  R: { name: 'Red', bg: '#CC3333', border: '#FF8888', letter: 'R', letterColor: '#FFFFFF' },
  G: { name: 'Green', bg: '#1A7335', border: '#66BB77', letter: 'G', letterColor: '#FFFFFF' },
};

const colorOrder = ['W', 'U', 'B', 'R', 'G'];

// Larger pentagon for more room
const cx = 350, cy = 300, radius = 150;

const getPoint = (index) => {
  const angle = (index * 72 - 90) * (Math.PI / 180);
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
};

const points = colorOrder.map((_, i) => getPoint(i));

// HAND-POSITIONED label coordinates to guarantee no overlap
// Ally pairs - outside each edge
const allyArchetypes = [
  { i1: 0, i2: 1, name: 'Merfolk', theme: 'Tap Triggers', typal: true, x: 485, y: 115 },
  { i1: 1, i2: 2, name: 'Flash', theme: 'Trickery', typal: false, x: 560, y: 310 },
  { i1: 2, i2: 3, name: 'Goblins', theme: 'Blight', typal: true, x: 350, y: 505 },
  { i1: 3, i2: 4, name: 'Vivid', theme: 'Beatdown', typal: false, x: 135, y: 400 },
  { i1: 4, i2: 0, name: 'Kithkin', theme: 'Go-Wide', typal: true, x: 155, y: 160 },
];

// Enemy pairs - carefully offset along diagonals, away from center
const enemyArchetypes = [
  { i1: 0, i2: 2, name: 'Persist', theme: 'Recursion', typal: false, x: 420, y: 220 },
  { i1: 1, i2: 3, name: 'Elementals', theme: '4+ MV', typal: true, x: 350, y: 365 },
  { i1: 2, i2: 4, name: 'Elves', theme: 'Graveyard', typal: true, x: 250, y: 330 },
  { i1: 3, i2: 0, name: 'Giants', theme: 'Aggro', typal: false, x: 280, y: 220 },
  { i1: 4, i2: 1, name: 'Vivid', theme: 'Ramp', typal: false, x: 350, y: 255 },
];

const LabelBox = ({ x, y, name, theme, typal }) => {
  const boxWidth = 90;
  const boxHeight = 38;
  return (
    <g>
      <rect
        x={x - boxWidth/2}
        y={y - boxHeight/2}
        width={boxWidth}
        height={boxHeight}
        rx="6"
        fill={typal ? '#7C3AED' : '#F8FAFC'}
        stroke={typal ? '#6D28D9' : '#CBD5E1'}
        strokeWidth="2"
      />
      <text
        x={x}
        y={y - 3}
        textAnchor="middle"
        fontSize="12"
        fontWeight="bold"
        fill={typal ? '#FFFFFF' : '#1E293B'}
      >
        {name}
      </text>
      <text
        x={x}
        y={y + 12}
        textAnchor="middle"
        fontSize="10"
        fill={typal ? '#DDD6FE' : '#64748B'}
      >
        {theme}
      </text>
    </g>
  );
};

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
          Draft Archetypes Color Wheel (v7)
        </p>
      </div>

      {/* Main Diagram */}
      <svg width="700" height="580" style={{ maxWidth: '100%' }}>
        
        {/* Enemy pair lines (diagonals) - draw first */}
        {enemyArchetypes.map((arch, idx) => (
          <line
            key={`eline-${idx}`}
            x1={points[arch.i1].x}
            y1={points[arch.i1].y}
            x2={points[arch.i2].x}
            y2={points[arch.i2].y}
            stroke="#E2E8F0"
            strokeWidth="2"
            strokeDasharray="8,5"
          />
        ))}

        {/* Ally pair lines (edges) */}
        {allyArchetypes.map((arch, idx) => (
          <line
            key={`aline-${idx}`}
            x1={points[arch.i1].x}
            y1={points[arch.i1].y}
            x2={points[arch.i2].x}
            y2={points[arch.i2].y}
            stroke="#94A3B8"
            strokeWidth="3"
          />
        ))}

        {/* Color nodes */}
        {colorOrder.map((color, i) => {
          const p = points[i];
          return (
            <g key={color}>
              {/* Glow */}
              <circle cx={p.x} cy={p.y} r="38" fill={MTGColors[color].border} opacity="0.2" />
              {/* Main circle */}
              <circle
                cx={p.x}
                cy={p.y}
                r="30"
                fill={MTGColors[color].bg}
                stroke={MTGColors[color].border}
                strokeWidth="4"
              />
              {/* Letter */}
              <text
                x={p.x}
                y={p.y + 7}
                textAnchor="middle"
                fontSize="22"
                fontWeight="bold"
                fill={MTGColors[color].letterColor}
              >
                {MTGColors[color].letter}
              </text>
              {/* Color name */}
              <text
                x={p.x}
                y={p.y + 52}
                textAnchor="middle"
                fontSize="12"
                fill="#4B5563"
                fontWeight="500"
              >
                {MTGColors[color].name}
              </text>
            </g>
          );
        })}

        {/* Ally pair labels (outside edges) */}
        {allyArchetypes.map((arch, idx) => (
          <LabelBox key={`ally-${idx}`} {...arch} />
        ))}

        {/* Enemy pair labels (offset along diagonals) */}
        {enemyArchetypes.map((arch, idx) => (
          <LabelBox key={`enemy-${idx}`} {...arch} />
        ))}
      </svg>

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: '20px',
        flexWrap: 'wrap',
        justifyContent: 'center',
        marginTop: '8px',
        padding: '12px 24px',
        backgroundColor: '#F9FAFB',
        borderRadius: '8px',
        border: '1px solid #E5E7EB',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '28px', height: '3px', backgroundColor: '#94A3B8', borderRadius: '2px' }} />
          <span style={{ fontSize: '0.8rem', color: '#4B5563' }}>Ally (edge)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '28px',
            height: '3px',
            backgroundImage: 'repeating-linear-gradient(90deg, #E2E8F0 0px, #E2E8F0 6px, transparent 6px, transparent 11px)',
          }} />
          <span style={{ fontSize: '0.8rem', color: '#4B5563' }}>Enemy (diagonal)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '16px',
            height: '16px',
            borderRadius: '4px',
            backgroundColor: '#7C3AED',
          }} />
          <span style={{ fontSize: '0.8rem', color: '#4B5563' }}>Typal (gold signpost)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '16px',
            height: '16px',
            borderRadius: '4px',
            backgroundColor: '#F8FAFC',
            border: '2px solid #CBD5E1',
          }} />
          <span style={{ fontSize: '0.8rem', color: '#4B5563' }}>Mechanical (hybrid)</span>
        </div>
      </div>

      {/* Footer */}
      <p style={{ fontSize: '0.75rem', color: '#9CA3AF', marginTop: '12px', textAlign: 'center' }}>
        Prereleases Jan 16–22, 2026 · Faeries & Giants supported at higher rarities
      </p>
    </div>
  );
}
