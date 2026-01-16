/**
 * Lorwyn Eclipsed Draft Archetypes - Color Wheel Visualization
 * v2 - Clean uniform style
 *    - All lines now uniform style (removed typal/mechanical distinction)
 *    - Removed emoji icons from labels
 *    - Fixed label overlapping with staggered positioning for diagonal lines
 * 
 * v1 - Initial version
 *    - Pentagon layout with WUBRG arrangement
 *    - Typal archetypes shown with glowing purple lines
 *    - Mechanical archetypes shown with faint gray lines
 *    - Solid lines for ally pairs, dashed for enemy pairs
 *    - Emoji icons in archetype labels
 */

import React from 'react';

const MTGColors = {
  W: { name: 'White', bg: '#F9FAF4', accent: '#F8E7B9', symbol: '☀️', hex: '#F9F5E8' },
  U: { name: 'Blue', bg: '#0E68AB', accent: '#AAE0FA', symbol: '💧', hex: '#0E68AB' },
  B: { name: 'Black', bg: '#393B3A', accent: '#C9C5C2', symbol: '💀', hex: '#393B3A' },
  R: { name: 'Red', bg: '#D32029', accent: '#F9AA8F', symbol: '🔥', hex: '#D32029' },
  G: { name: 'Green', bg: '#00733E', accent: '#9BD3AE', symbol: '🌲', hex: '#00733E' },
};

const colorOrder = ['W', 'U', 'B', 'R', 'G'];
const cx = 300, cy = 280, radius = 180;

const getPoint = (index) => {
  const angle = (index * 72 - 90) * (Math.PI / 180);
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
};

const points = colorOrder.map((_, i) => getPoint(i));

// Archetypes with positioning hints for non-overlapping labels
// labelOffset: how far along the line (0.5 = middle, <0.5 = toward first color, >0.5 = toward second)
const archetypeData = [
  { colors: [0, 1], tribe: 'Merfolk', theme: 'Tap Triggers', typal: true, labelOffset: 0.5 },
  { colors: [1, 2], tribe: null, theme: 'Flash Trickery', typal: false, labelOffset: 0.5 },
  { colors: [2, 3], tribe: 'Goblins', theme: 'Blight Sacrifice', typal: true, labelOffset: 0.5 },
  { colors: [3, 4], tribe: null, theme: 'Vivid Beatdown', typal: false, labelOffset: 0.5 },
  { colors: [4, 0], tribe: 'Kithkin', theme: 'Go-Wide Tokens', typal: true, labelOffset: 0.5 },
  // Enemy pairs - stagger positions to avoid overlap
  { colors: [0, 2], tribe: null, theme: 'Persist Recursion', typal: false, labelOffset: 0.35 },
  { colors: [1, 3], tribe: 'Elementals', theme: 'Big Spells 4+', typal: true, labelOffset: 0.65 },
  { colors: [2, 4], tribe: 'Elves', theme: 'Graveyard Value', typal: true, labelOffset: 0.35 },
  { colors: [3, 0], tribe: null, theme: 'Giants Aggro', typal: false, labelOffset: 0.65 },
  { colors: [4, 1], tribe: null, theme: 'Vivid Ramp', typal: false, labelOffset: 0.5 },
];

const isAllyPair = (i1, i2) => {
  const diff = Math.abs(i1 - i2);
  return diff === 1 || diff === 4;
};

export default function LorwynColorWheel() {
  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(145deg, #0f172a 0%, #1e1b4b 50%, #172554 100%)',
      padding: '20px',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '16px' }}>
        <h1 style={{ 
          color: '#fff', 
          fontSize: '1.8rem', 
          margin: '0 0 4px 0',
          background: 'linear-gradient(90deg, #fff, #c4b5fd)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          Lorwyn Eclipsed (v2)
        </h1>
        <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
          Draft Archetypes Color Wheel
        </p>
      </div>

      {/* Legend */}
      <div style={{ 
        display: 'flex', 
        gap: '24px', 
        marginBottom: '12px',
        fontSize: '0.8rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ 
            width: '40px', 
            height: '3px', 
            background: 'rgba(148,163,184,0.6)',
            borderRadius: '2px',
          }}/>
          <span style={{ color: '#94a3b8' }}>Ally Colors (Edge)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ 
            width: '40px', 
            height: '3px', 
            background: 'rgba(148,163,184,0.6)',
            borderRadius: '2px',
            backgroundImage: 'repeating-linear-gradient(90deg, transparent, transparent 4px, #0f172a 4px, #0f172a 8px)'
          }}/>
          <span style={{ color: '#94a3b8' }}>Enemy Colors (Diagonal)</span>
        </div>
      </div>

      {/* Main SVG */}
      <svg width="600" height="560" style={{ overflow: 'visible' }}>
        {/* Connection lines - all uniform now */}
        {archetypeData.map((arch, idx) => {
          const [i1, i2] = arch.colors;
          const p1 = points[i1];
          const p2 = points[i2];
          const isAlly = isAllyPair(i1, i2);
          
          return (
            <line
              key={idx}
              x1={p1.x}
              y1={p1.y}
              x2={p2.x}
              y2={p2.y}
              stroke="rgba(148,163,184,0.5)"
              strokeWidth="2"
              strokeDasharray={isAlly ? 'none' : '6,4'}
            />
          );
        })}

        {/* Archetype labels - no emojis, staggered positions */}
        {archetypeData.map((arch, idx) => {
          const [i1, i2] = arch.colors;
          const p1 = points[i1];
          const p2 = points[i2];
          const isAlly = isAllyPair(i1, i2);
          
          // Calculate position along the line based on labelOffset
          const t = arch.labelOffset;
          let mid = {
            x: p1.x + (p2.x - p1.x) * t,
            y: p1.y + (p2.y - p1.y) * t,
          };
          
          // For ally pairs, push outward slightly; for enemy pairs, they're already staggered
          if (isAlly) {
            // Push slightly outward from center
            const dx = mid.x - cx;
            const dy = mid.y - cy;
            const dist = Math.sqrt(dx * dx + dy * dy);
            mid.x += (dx / dist) * 15;
            mid.y += (dy / dist) * 15;
          }
          
          const displayName = arch.tribe || arch.theme.split(' ')[0];
          const displayTheme = arch.tribe ? arch.theme : arch.theme.split(' ').slice(1).join(' ');
          
          return (
            <g key={`label-${idx}`}>
              <rect
                x={mid.x - 46}
                y={mid.y - 16}
                width="92"
                height="32"
                rx="16"
                fill={arch.typal ? 'rgba(139,92,246,0.15)' : 'rgba(30,41,59,0.9)'}
                stroke={arch.typal ? 'rgba(167,139,250,0.3)' : 'rgba(71,85,105,0.3)'}
                strokeWidth="1"
              />
              <text
                x={mid.x}
                y={mid.y - 2}
                textAnchor="middle"
                fill={arch.typal ? '#e9d5ff' : '#94a3b8'}
                fontSize="10"
                fontWeight="600"
              >
                {displayName}
              </text>
              <text
                x={mid.x}
                y={mid.y + 10}
                textAnchor="middle"
                fill={arch.typal ? '#a78bfa' : '#64748b'}
                fontSize="8"
              >
                {displayTheme}
              </text>
            </g>
          );
        })}

        {/* Color nodes */}
        {colorOrder.map((color, i) => {
          const p = points[i];
          return (
            <g key={color}>
              <circle cx={p.x} cy={p.y} r="38" fill="none" stroke={MTGColors[color].hex} strokeWidth="2" opacity="0.3"/>
              <circle
                cx={p.x}
                cy={p.y}
                r="32"
                fill={MTGColors[color].bg}
                stroke={MTGColors[color].accent}
                strokeWidth="3"
                style={{ filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.4))' }}
              />
              <text x={p.x} y={p.y + 6} textAnchor="middle" fontSize="24">
                {MTGColors[color].symbol}
              </text>
              <text x={p.x} y={p.y + 52} textAnchor="middle" fill="#94a3b8" fontSize="12" fontWeight="500">
                {MTGColors[color].name}
              </text>
            </g>
          );
        })}

        {/* Center emblem */}
        <circle cx={cx} cy={cy} r="24" fill="rgba(30,41,59,0.8)" stroke="rgba(148,163,184,0.2)" strokeWidth="1"/>
        <text x={cx} y={cy - 4} textAnchor="middle" fill="#64748b" fontSize="9">ECL</text>
        <text x={cx} y={cy + 8} textAnchor="middle" fill="#475569" fontSize="8">2026</text>
      </svg>

      {/* Footer */}
      <div style={{ marginTop: '8px', textAlign: 'center', maxWidth: '500px' }}>
        <p style={{ color: '#64748b', fontSize: '0.75rem', margin: '0 0 4px 0' }}>
          <span style={{ color: '#c4b5fd' }}>Purple tint</span> = Typal archetype (Gold Signpost) • 
          <span style={{ color: '#64748b' }}> Gray</span> = Mechanical (Hybrid Only)
        </p>
        <p style={{ color: '#475569', fontSize: '0.7rem', margin: 0 }}>
          Prereleases Jan 16–22, 2026 • Faeries & Giants supported at higher rarities
        </p>
      </div>
    </div>
  );
}
