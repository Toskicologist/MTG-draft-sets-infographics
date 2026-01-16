/**
 * Lorwyn Eclipsed Draft Archetypes - Color Wheel Visualization
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

// Pentagon vertices - WUBRG clockwise from top
const colorOrder = ['W', 'U', 'B', 'R', 'G'];
const cx = 300, cy = 280, radius = 180;

// Calculate pentagon points
const getPoint = (index) => {
  const angle = (index * 72 - 90) * (Math.PI / 180);
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
};

const points = colorOrder.map((_, i) => getPoint(i));

// All archetypes with color indices
const archetypeData = [
  { colors: [0, 1], tribe: 'Merfolk', theme: 'Tap Triggers', typal: true, emoji: '🧜' },
  { colors: [1, 2], tribe: null, theme: 'Flash Trickery', typal: false, emoji: '🦋' },
  { colors: [2, 3], tribe: 'Goblins', theme: 'Blight Sacrifice', typal: true, emoji: '👺' },
  { colors: [3, 4], tribe: null, theme: 'Vivid Beatdown', typal: false, emoji: '🌈' },
  { colors: [4, 0], tribe: 'Kithkin', theme: 'Go-Wide Tokens', typal: true, emoji: '🏠' },
  { colors: [0, 2], tribe: null, theme: 'Persist Recursion', typal: false, emoji: '♻️' },
  { colors: [1, 3], tribe: 'Elementals', theme: 'Big Spells 4+', typal: true, emoji: '🌊' },
  { colors: [2, 4], tribe: 'Elves', theme: 'Graveyard Value', typal: true, emoji: '🧝' },
  { colors: [3, 0], tribe: null, theme: 'Giants Aggro', typal: false, emoji: '🗿' },
  { colors: [4, 1], tribe: null, theme: 'Vivid Ramp', typal: false, emoji: '✨' },
];

// Determine if pair is ally (adjacent on wheel) or enemy (diagonal)
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
          Lorwyn Eclipsed
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
            height: '4px', 
            background: 'linear-gradient(90deg, #a78bfa, #8b5cf6)',
            borderRadius: '2px',
            boxShadow: '0 0 10px rgba(167,139,250,0.5)'
          }}/>
          <span style={{ color: '#c4b5fd' }}>Typal (Gold Signpost)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ 
            width: '40px', 
            height: '2px', 
            background: 'rgba(148,163,184,0.4)',
            borderRadius: '2px'
          }}/>
          <span style={{ color: '#64748b' }}>Mechanical (Hybrid Only)</span>
        </div>
      </div>

      {/* Main SVG */}
      <svg width="600" height="560" style={{ overflow: 'visible' }}>
        <defs>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
          <linearGradient id="typalGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#a78bfa"/>
            <stop offset="100%" stopColor="#8b5cf6"/>
          </linearGradient>
        </defs>

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
              stroke={arch.typal ? 'url(#typalGrad)' : 'rgba(148,163,184,0.25)'}
              strokeWidth={arch.typal ? 4 : 2}
              strokeDasharray={isAlly ? 'none' : '8,4'}
              filter={arch.typal ? 'url(#glow)' : 'none'}
            />
          );
        })}

        {/* Archetype labels */}
        {archetypeData.map((arch, idx) => {
          const [i1, i2] = arch.colors;
          const p1 = points[i1];
          const p2 = points[i2];
          const isAlly = isAllyPair(i1, i2);
          
          const pullFactor = isAlly ? 0 : 0.25;
          const mid = {
            x: (p1.x + p2.x) / 2 + ((cx - (p1.x + p2.x) / 2) * pullFactor),
            y: (p1.y + p2.y) / 2 + ((cy - (p1.y + p2.y) / 2) * pullFactor),
          };
          
          return (
            <g key={`label-${idx}`}>
              <rect
                x={mid.x - 52}
                y={mid.y - 18}
                width="104"
                height="36"
                rx="18"
                fill={arch.typal ? 'rgba(139,92,246,0.2)' : 'rgba(30,41,59,0.9)'}
                stroke={arch.typal ? 'rgba(167,139,250,0.4)' : 'rgba(71,85,105,0.3)'}
                strokeWidth="1"
              />
              <text x={mid.x - 36} y={mid.y + 5} textAnchor="middle" fontSize="14">
                {arch.emoji}
              </text>
              <text
                x={mid.x + 8}
                y={mid.y - 4}
                textAnchor="middle"
                fill={arch.typal ? '#e9d5ff' : '#94a3b8'}
                fontSize="10"
                fontWeight="600"
              >
                {arch.tribe || arch.theme.split(' ')[0]}
              </text>
              <text
                x={mid.x + 8}
                y={mid.y + 10}
                textAnchor="middle"
                fill={arch.typal ? '#a78bfa' : '#64748b'}
                fontSize="9"
              >
                {arch.tribe ? arch.theme : arch.theme.split(' ').slice(1).join(' ')}
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
          <span style={{ color: '#94a3b8' }}>Solid lines</span> = Ally colors • 
          <span style={{ color: '#94a3b8' }}> Dashed lines</span> = Enemy colors
        </p>
        <p style={{ color: '#475569', fontSize: '0.7rem', margin: 0 }}>
          Faeries (UB flavor) & Giants (RW) supported at rare for Constructed
        </p>
      </div>
    </div>
  );
}
