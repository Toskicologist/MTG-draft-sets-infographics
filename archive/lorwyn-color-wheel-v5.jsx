/**
 * Lorwyn Eclipsed Draft Archetypes - Color Wheel Visualization
 * v5 - Accessibility-focused redesign
 *    - Ally pair labels positioned OUTSIDE each pentagon edge (no overlap possible)
 *    - Enemy pair archetypes shown in separate list below (avoids center congestion)
 *    - Emoji icons restored on color nodes
 *    - White background with WCAG AA contrast ratios (4.5:1+)
 *    - Larger text sizes for readability
 *    - Clear visual association between labels and connections
 *
 * v4 - White background, fixed positions (still overlapped)
 * v3 - Static PNG attempt (font/overlap issues)
 * v2 - Uniform lines, no emojis, attempted stagger
 * v1 - Initial React version
 */

import React from 'react';

const MTGColors = {
  W: { name: 'White', bg: '#F9FAF4', accent: '#D4AF37', symbol: '☀️', textColor: '#92400e' },
  U: { name: 'Blue', bg: '#1d4ed8', accent: '#93c5fd', symbol: '💧', textColor: '#FFFFFF' },
  B: { name: 'Black', bg: '#1f2937', accent: '#9ca3af', symbol: '💀', textColor: '#FFFFFF' },
  R: { name: 'Red', bg: '#dc2626', accent: '#fca5a5', symbol: '🔥', textColor: '#FFFFFF' },
  G: { name: 'Green', bg: '#16a34a', accent: '#86efac', symbol: '🌲', textColor: '#FFFFFF' },
};

const colorOrder = ['W', 'U', 'B', 'R', 'G'];
const cx = 300, cy = 260, radius = 140;

const getPoint = (index) => {
  const angle = (index * 72 - 90) * (Math.PI / 180);
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
};

const points = colorOrder.map((_, i) => getPoint(i));

// Ally pairs - positioned outside each edge
const allyPairs = [
  { colors: [0, 1], tribe: 'Merfolk', theme: 'Tap Triggers', typal: true },
  { colors: [1, 2], tribe: null, theme: 'Flash & Trickery', typal: false },
  { colors: [2, 3], tribe: 'Goblins', theme: 'Blight & Sacrifice', typal: true },
  { colors: [3, 4], tribe: null, theme: 'Vivid Beatdown', typal: false },
  { colors: [4, 0], tribe: 'Kithkin', theme: 'Go-Wide Tokens', typal: true },
];

// Enemy pairs - shown in list below
const enemyPairs = [
  { colors: ['W', 'B'], tribe: null, theme: 'Persist & Recursion', typal: false },
  { colors: ['U', 'R'], tribe: 'Elementals', theme: 'Big Spells (4+ MV)', typal: true },
  { colors: ['B', 'G'], tribe: 'Elves', theme: 'Graveyard Value', typal: true },
  { colors: ['R', 'W'], tribe: null, theme: 'Giants Aggro', typal: false },
  { colors: ['G', 'U'], tribe: null, theme: 'Vivid Ramp', typal: false },
];

// Calculate label position outside the midpoint of an edge
const getEdgeLabelPos = (i1, i2) => {
  const p1 = points[i1];
  const p2 = points[i2];
  const midX = (p1.x + p2.x) / 2;
  const midY = (p1.y + p2.y) / 2;
  
  const dx = midX - cx;
  const dy = midY - cy;
  const dist = Math.sqrt(dx * dx + dy * dy);
  const pushDist = 75;
  
  return {
    x: midX + (dx / dist) * pushDist,
    y: midY + (dy / dist) * pushDist,
  };
};

const ColorBadge = ({ color, size = 24 }) => (
  <span style={{
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: size,
    height: size,
    borderRadius: '50%',
    background: MTGColors[color].bg,
    border: `2px solid ${MTGColors[color].accent}`,
    fontSize: size * 0.5,
    marginRight: 4,
  }}>
    {MTGColors[color].symbol}
  </span>
);

export default function LorwynColorWheel() {
  return (
    <div style={{ 
      minHeight: '100vh', 
      background: '#ffffff',
      padding: '24px',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '20px' }}>
        <h1 style={{ color: '#0f172a', fontSize: '2rem', margin: '0 0 4px 0', fontWeight: '700' }}>
          Lorwyn Eclipsed
        </h1>
        <p style={{ color: '#475569', margin: 0, fontSize: '1rem' }}>
          Draft Archetypes by Color Pair
        </p>
      </div>

      {/* Main Pentagon with Ally Pairs */}
      <svg width="600" height="460" style={{ overflow: 'visible' }}>
        {/* Draw ally pair lines (edges) */}
        {allyPairs.map((arch, idx) => {
          const [i1, i2] = arch.colors;
          const p1 = points[i1];
          const p2 = points[i2];
          return (
            <line
              key={`ally-${idx}`}
              x1={p1.x} y1={p1.y}
              x2={p2.x} y2={p2.y}
              stroke="#64748b"
              strokeWidth="2.5"
            />
          );
        })}

        {/* Draw enemy pair lines (diagonals) - lighter */}
        {[[0,2], [1,3], [2,4], [3,0], [4,1]].map(([i1, i2], idx) => {
          const p1 = points[i1];
          const p2 = points[i2];
          return (
            <line
              key={`enemy-${idx}`}
              x1={p1.x} y1={p1.y}
              x2={p2.x} y2={p2.y}
              stroke="#cbd5e1"
              strokeWidth="1.5"
              strokeDasharray="6,4"
            />
          );
        })}

        {/* Ally pair labels - outside each edge */}
        {allyPairs.map((arch, idx) => {
          const [i1, i2] = arch.colors;
          const pos = getEdgeLabelPos(i1, i2);
          const displayName = arch.tribe || arch.theme.split('&')[0].trim();
          const displayTheme = arch.tribe ? arch.theme : arch.theme.split('&')[1]?.trim() || '';
          
          return (
            <g key={`label-${idx}`}>
              <rect
                x={pos.x - 60}
                y={pos.y - 22}
                width="120"
                height="44"
                rx="8"
                fill={arch.typal ? '#7c3aed' : '#f8fafc'}
                stroke={arch.typal ? '#6d28d9' : '#e2e8f0'}
                strokeWidth="2"
              />
              <text
                x={pos.x}
                y={pos.y - 4}
                textAnchor="middle"
                fill={arch.typal ? '#ffffff' : '#1e293b'}
                fontSize="14"
                fontWeight="600"
              >
                {displayName}
              </text>
              <text
                x={pos.x}
                y={pos.y + 14}
                textAnchor="middle"
                fill={arch.typal ? '#e9d5ff' : '#64748b'}
                fontSize="11"
              >
                {displayTheme}
              </text>
            </g>
          );
        })}

        {/* Color nodes with emoji icons */}
        {colorOrder.map((color, i) => {
          const p = points[i];
          return (
            <g key={color}>
              {/* Outer glow */}
              <circle cx={p.x} cy={p.y} r="44" fill={MTGColors[color].accent} opacity="0.25"/>
              {/* Main circle */}
              <circle
                cx={p.x}
                cy={p.y}
                r="36"
                fill={MTGColors[color].bg}
                stroke={MTGColors[color].accent}
                strokeWidth="4"
              />
              {/* Emoji */}
              <text x={p.x} y={p.y + 8} textAnchor="middle" fontSize="28">
                {MTGColors[color].symbol}
              </text>
              {/* Color name */}
              <text 
                x={p.x} y={p.y + 60} 
                textAnchor="middle" 
                fill="#334155" 
                fontSize="14" 
                fontWeight="500"
              >
                {MTGColors[color].name}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Enemy Pairs Section - Separate list to avoid overlap */}
      <div style={{ 
        marginTop: '16px',
        width: '100%',
        maxWidth: '600px',
      }}>
        <h2 style={{ 
          fontSize: '0.9rem', 
          color: '#64748b', 
          textAlign: 'center',
          margin: '0 0 12px 0',
          fontWeight: '500',
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          Enemy Color Pairs (Diagonals)
        </h2>
        <div style={{ 
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '10px',
        }}>
          {enemyPairs.map((arch, idx) => (
            <div 
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '10px 12px',
                borderRadius: '8px',
                background: arch.typal ? '#7c3aed' : '#f8fafc',
                border: `2px solid ${arch.typal ? '#6d28d9' : '#e2e8f0'}`,
              }}
            >
              <div style={{ display: 'flex', marginRight: '10px' }}>
                <ColorBadge color={arch.colors[0]} size={28} />
                <ColorBadge color={arch.colors[1]} size={28} />
              </div>
              <div>
                <div style={{ 
                  fontWeight: '600', 
                  fontSize: '0.9rem',
                  color: arch.typal ? '#ffffff' : '#1e293b',
                }}>
                  {arch.tribe || arch.theme.split('&')[0].trim()}
                </div>
                <div style={{ 
                  fontSize: '0.75rem',
                  color: arch.typal ? '#e9d5ff' : '#64748b',
                }}>
                  {arch.tribe ? arch.theme : (arch.theme.split('&')[1]?.trim() || arch.theme)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div style={{ 
        marginTop: '20px',
        display: 'flex',
        gap: '24px',
        flexWrap: 'wrap',
        justifyContent: 'center',
        padding: '12px 20px',
        background: '#f8fafc',
        borderRadius: '8px',
        border: '1px solid #e2e8f0',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '32px', height: '3px', background: '#64748b', borderRadius: '2px' }}/>
          <span style={{ color: '#475569', fontSize: '0.85rem' }}>Ally pairs (edges)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ 
            width: '32px', height: '3px', 
            backgroundImage: 'repeating-linear-gradient(90deg, #cbd5e1, #cbd5e1 4px, transparent 4px, transparent 8px)'
          }}/>
          <span style={{ color: '#475569', fontSize: '0.85rem' }}>Enemy pairs (diagonals)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '18px', height: '18px', borderRadius: '4px', background: '#7c3aed' }}/>
          <span style={{ color: '#475569', fontSize: '0.85rem' }}>Typal (Gold Signpost)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '18px', height: '18px', borderRadius: '4px', background: '#f8fafc', border: '2px solid #e2e8f0' }}/>
          <span style={{ color: '#475569', fontSize: '0.85rem' }}>Mechanical (Hybrid Only)</span>
        </div>
      </div>

      {/* Footer */}
      <p style={{ color: '#64748b', fontSize: '0.8rem', marginTop: '16px', textAlign: 'center' }}>
        Prereleases Jan 16–22, 2026 · Faeries & Giants supported at higher rarities
      </p>
    </div>
  );
}
