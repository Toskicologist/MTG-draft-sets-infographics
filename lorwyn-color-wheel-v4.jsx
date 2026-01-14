/**
 * Lorwyn Eclipsed Draft Archetypes - Color Wheel Visualization
 * v4 - White background, labels outside pentagon
 *    - White/light background for better readability
 *    - All labels positioned OUTSIDE the pentagon to eliminate overlap
 *    - Clean professional appearance
 *
 * v3 - Static PNG attempt (had font/overlap issues)
 * v2 - Uniform lines, no emojis, attempted stagger (still overlapped)
 * v1 - Initial React version with glowing lines and emojis
 */

import React from 'react';

const MTGColors = {
  W: { name: 'White', bg: '#F9FAF4', accent: '#D4AF37', symbol: 'W', textColor: '#B8860B' },
  U: { name: 'Blue', bg: '#0E68AB', accent: '#AAE0FA', symbol: 'U', textColor: '#FFFFFF' },
  B: { name: 'Black', bg: '#393B3A', accent: '#888888', symbol: 'B', textColor: '#FFFFFF' },
  R: { name: 'Red', bg: '#D32029', accent: '#F9AA8F', symbol: 'R', textColor: '#FFFFFF' },
  G: { name: 'Green', bg: '#00733E', accent: '#9BD3AE', symbol: 'G', textColor: '#FFFFFF' },
};

const colorOrder = ['W', 'U', 'B', 'R', 'G'];
const cx = 300, cy = 300, radius = 150;

const getPoint = (index) => {
  const angle = (index * 72 - 90) * (Math.PI / 180);
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
};

const points = colorOrder.map((_, i) => getPoint(i));

// Archetypes with FIXED external label positions (x, y offsets from center)
const archetypeData = [
  // Ally pairs - labels outside edges
  { colors: [0, 1], tribe: 'Merfolk', theme: 'Tap Triggers', typal: true, labelPos: { x: 390, y: 140 } },
  { colors: [1, 2], tribe: null, theme: 'Flash Trickery', typal: false, labelPos: { x: 480, y: 320 } },
  { colors: [2, 3], tribe: 'Goblins', theme: 'Blight Sacrifice', typal: true, labelPos: { x: 370, y: 500 } },
  { colors: [3, 4], tribe: null, theme: 'Vivid Beatdown', typal: false, labelPos: { x: 120, y: 440 } },
  { colors: [4, 0], tribe: 'Kithkin', theme: 'Go-Wide Tokens', typal: true, labelPos: { x: 70, y: 200 } },
  // Enemy pairs - labels well separated
  { colors: [0, 2], tribe: null, theme: 'Persist Recursion', typal: false, labelPos: { x: 420, y: 230 } },
  { colors: [1, 3], tribe: 'Elementals', theme: 'Big Spells 4+', typal: true, labelPos: { x: 300, y: 300 } },
  { colors: [2, 4], tribe: 'Elves', theme: 'Graveyard Value', typal: true, labelPos: { x: 180, y: 360 } },
  { colors: [3, 0], tribe: null, theme: 'Giants Aggro', typal: false, labelPos: { x: 180, y: 240 } },
  { colors: [4, 1], tribe: null, theme: 'Vivid Ramp', typal: false, labelPos: { x: 420, y: 370 } },
];

const isAllyPair = (i1, i2) => {
  const diff = Math.abs(i1 - i2);
  return diff === 1 || diff === 4;
};

export default function LorwynColorWheel() {
  return (
    <div style={{ 
      minHeight: '100vh', 
      background: '#FFFFFF',
      padding: '20px',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '16px' }}>
        <h1 style={{ 
          color: '#1e293b', 
          fontSize: '1.8rem', 
          margin: '0 0 4px 0',
        }}>
          Lorwyn Eclipsed
        </h1>
        <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
          Draft Archetypes Color Wheel (v4)
        </p>
      </div>

      {/* Legend */}
      <div style={{ 
        display: 'flex', 
        gap: '24px', 
        marginBottom: '16px',
        fontSize: '0.8rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '40px', height: '3px', background: '#94a3b8', borderRadius: '2px' }}/>
          <span style={{ color: '#64748b' }}>Ally pairs</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ 
            width: '40px', height: '3px', 
            backgroundImage: 'repeating-linear-gradient(90deg, #94a3b8, #94a3b8 6px, transparent 6px, transparent 10px)'
          }}/>
          <span style={{ color: '#64748b' }}>Enemy pairs</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ 
            width: '16px', height: '16px', borderRadius: '4px',
            background: '#7c3aed', 
          }}/>
          <span style={{ color: '#64748b' }}>Typal</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ 
            width: '16px', height: '16px', borderRadius: '4px',
            background: '#e2e8f0', border: '1px solid #cbd5e1'
          }}/>
          <span style={{ color: '#64748b' }}>Mechanical</span>
        </div>
      </div>

      {/* Main SVG */}
      <svg width="600" height="600" style={{ overflow: 'visible' }}>
        {/* Connection lines */}
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
              stroke="#94a3b8"
              strokeWidth="2"
              strokeDasharray={isAlly ? 'none' : '8,4'}
            />
          );
        })}

        {/* Archetype labels at fixed positions */}
        {archetypeData.map((arch, idx) => {
          const { x, y } = arch.labelPos;
          const displayName = arch.tribe || arch.theme.split(' ')[0];
          const displayTheme = arch.tribe ? arch.theme : arch.theme.split(' ').slice(1).join(' ');
          
          return (
            <g key={`label-${idx}`}>
              <rect
                x={x - 55}
                y={y - 20}
                width="110"
                height="40"
                rx="8"
                fill={arch.typal ? '#7c3aed' : '#f1f5f9'}
                stroke={arch.typal ? '#6d28d9' : '#cbd5e1'}
                strokeWidth="1.5"
              />
              <text
                x={x}
                y={y - 3}
                textAnchor="middle"
                fill={arch.typal ? '#ffffff' : '#334155'}
                fontSize="12"
                fontWeight="600"
              >
                {displayName}
              </text>
              <text
                x={x}
                y={y + 12}
                textAnchor="middle"
                fill={arch.typal ? '#e9d5ff' : '#64748b'}
                fontSize="10"
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
              <circle 
                cx={p.x} cy={p.y} r="42" 
                fill="none" 
                stroke={MTGColors[color].accent} 
                strokeWidth="2" 
                opacity="0.4"
              />
              <circle
                cx={p.x}
                cy={p.y}
                r="36"
                fill={MTGColors[color].bg}
                stroke={MTGColors[color].accent}
                strokeWidth="3"
                style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.15))' }}
              />
              <text 
                x={p.x} y={p.y + 8} 
                textAnchor="middle" 
                fontSize="28" 
                fontWeight="bold"
                fill={MTGColors[color].textColor}
              >
                {MTGColors[color].symbol}
              </text>
              <text 
                x={p.x} y={p.y + 58} 
                textAnchor="middle" 
                fill="#475569" 
                fontSize="13" 
                fontWeight="500"
              >
                {MTGColors[color].name}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Footer */}
      <div style={{ marginTop: '8px', textAlign: 'center' }}>
        <p style={{ color: '#64748b', fontSize: '0.8rem', margin: 0 }}>
          Prereleases Jan 16–22, 2026 · Faeries & Giants supported at higher rarities
        </p>
      </div>
    </div>
  );
}
