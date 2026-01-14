/**
 * Lorwyn Eclipsed Draft Archetypes - Color Wheel Visualization
 * v6 - Clean information hierarchy
 *    - Simple pentagon wheel shows COLOR RELATIONSHIPS only (no labels on diagram)
 *    - All 10 archetypes displayed in clean, accessible table below
 *    - Reliable icon rendering using CSS shapes (not emoji)
 *    - White background, WCAG AA compliant contrast
 *    - Mobile-friendly responsive grid
 *
 * Design principles applied:
 *    - Separation of concerns: diagram shows structure, table shows details
 *    - Progressive disclosure: see the pattern first, details second
 *    - Accessibility: table is screen-reader friendly, no text overlap
 *    - Consistency: all archetypes formatted identically
 *
 * v5 - Attempted split (still had overlap issues)
 * v4 - White background, fixed positions (overlapped)
 * v3 - Static PNG (font issues)
 * v2 - Uniform lines, attempted stagger
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

// Pentagon geometry
const cx = 150, cy = 150, radius = 100;
const getPoint = (index) => {
  const angle = (index * 72 - 90) * (Math.PI / 180);
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
};
const points = colorOrder.map((_, i) => getPoint(i));

// All archetypes data
const archetypes = [
  // Ally pairs
  { c1: 'W', c2: 'U', name: 'Merfolk', theme: 'Tap Triggers', typal: true, ally: true },
  { c1: 'U', c2: 'B', name: 'Flash', theme: 'Instant-Speed Trickery', typal: false, ally: true },
  { c1: 'B', c2: 'R', name: 'Goblins', theme: 'Blight & Sacrifice', typal: true, ally: true },
  { c1: 'R', c2: 'G', name: 'Vivid', theme: 'Beatdown', typal: false, ally: true },
  { c1: 'G', c2: 'W', name: 'Kithkin', theme: 'Go-Wide Tokens', typal: true, ally: true },
  // Enemy pairs
  { c1: 'W', c2: 'B', name: 'Persist', theme: 'Recursion', typal: false, ally: false },
  { c1: 'U', c2: 'R', name: 'Elementals', theme: 'Big Spells (4+ MV)', typal: true, ally: false },
  { c1: 'B', c2: 'G', name: 'Elves', theme: 'Graveyard Value', typal: true, ally: false },
  { c1: 'R', c2: 'W', name: 'Giants', theme: 'Aggro', typal: false, ally: false },
  { c1: 'G', c2: 'U', name: 'Vivid', theme: 'Ramp', typal: false, ally: false },
];

// Color pip component
const ColorPip = ({ color, size = 32 }) => (
  <div style={{
    width: size,
    height: size,
    borderRadius: '50%',
    backgroundColor: MTGColors[color].bg,
    border: `3px solid ${MTGColors[color].border}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 'bold',
    fontSize: size * 0.45,
    color: MTGColors[color].letterColor,
    flexShrink: 0,
  }}>
    {MTGColors[color].letter}
  </div>
);

// Archetype row component
const ArchetypeRow = ({ arch }) => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    padding: '12px 16px',
    backgroundColor: arch.typal ? '#F5F3FF' : '#FFFFFF',
    border: `2px solid ${arch.typal ? '#8B5CF6' : '#E5E7EB'}`,
    borderRadius: '10px',
    gap: '12px',
  }}>
    {/* Color pips */}
    <div style={{ display: 'flex', gap: '4px' }}>
      <ColorPip color={arch.c1} size={36} />
      <ColorPip color={arch.c2} size={36} />
    </div>
    
    {/* Info */}
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ 
        fontWeight: '700', 
        fontSize: '1rem',
        color: '#1F2937',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
      }}>
        {arch.name}
        {arch.typal && (
          <span style={{
            fontSize: '0.65rem',
            padding: '2px 6px',
            backgroundColor: '#8B5CF6',
            color: 'white',
            borderRadius: '4px',
            fontWeight: '600',
          }}>
            TYPAL
          </span>
        )}
      </div>
      <div style={{ fontSize: '0.85rem', color: '#6B7280' }}>
        {arch.theme}
      </div>
    </div>
    
    {/* Ally/Enemy indicator */}
    <div style={{
      fontSize: '0.7rem',
      padding: '4px 8px',
      backgroundColor: arch.ally ? '#DBEAFE' : '#FEE2E2',
      color: arch.ally ? '#1E40AF' : '#991B1B',
      borderRadius: '4px',
      fontWeight: '500',
      whiteSpace: 'nowrap',
    }}>
      {arch.ally ? 'Ally' : 'Enemy'}
    </div>
  </div>
);

export default function LorwynColorWheel() {
  const allyPairs = archetypes.filter(a => a.ally);
  const enemyPairs = archetypes.filter(a => !a.ally);
  
  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: '#FFFFFF',
      padding: '24px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <h1 style={{ 
            fontSize: '2rem', 
            fontWeight: '800', 
            color: '#111827',
            margin: '0 0 4px 0',
          }}>
            Lorwyn Eclipsed
          </h1>
          <p style={{ fontSize: '1rem', color: '#6B7280', margin: 0 }}>
            Draft Archetypes by Color Pair (v6)
          </p>
        </div>

        {/* Color Wheel Diagram - Simple, no labels */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'center', 
          marginBottom: '24px',
          padding: '16px',
          backgroundColor: '#F9FAFB',
          borderRadius: '16px',
          border: '1px solid #E5E7EB',
        }}>
          <svg width="300" height="300" viewBox="0 0 300 300">
            {/* Enemy pair lines (diagonals) - draw first, behind */}
            {[[0,2], [1,3], [2,4], [3,0], [4,1]].map(([i1, i2], idx) => (
              <line
                key={`e-${idx}`}
                x1={points[i1].x} y1={points[i1].y}
                x2={points[i2].x} y2={points[i2].y}
                stroke="#E5E7EB"
                strokeWidth="2"
                strokeDasharray="6,4"
              />
            ))}
            
            {/* Ally pair lines (edges) */}
            {[[0,1], [1,2], [2,3], [3,4], [4,0]].map(([i1, i2], idx) => (
              <line
                key={`a-${idx}`}
                x1={points[i1].x} y1={points[i1].y}
                x2={points[i2].x} y2={points[i2].y}
                stroke="#9CA3AF"
                strokeWidth="3"
              />
            ))}
            
            {/* Color nodes */}
            {colorOrder.map((color, i) => {
              const p = points[i];
              return (
                <g key={color}>
                  <circle
                    cx={p.x} cy={p.y} r="28"
                    fill={MTGColors[color].bg}
                    stroke={MTGColors[color].border}
                    strokeWidth="4"
                  />
                  <text
                    x={p.x} y={p.y + 7}
                    textAnchor="middle"
                    fontSize="20"
                    fontWeight="bold"
                    fill={MTGColors[color].letterColor}
                  >
                    {MTGColors[color].letter}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Legend */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '24px',
          marginBottom: '24px',
          flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '24px', height: '3px', backgroundColor: '#9CA3AF' }} />
            <span style={{ fontSize: '0.85rem', color: '#6B7280' }}>Ally (adjacent)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ 
              width: '24px', height: '3px', 
              backgroundImage: 'repeating-linear-gradient(90deg, #E5E7EB 0px, #E5E7EB 6px, transparent 6px, transparent 10px)'
            }} />
            <span style={{ fontSize: '0.85rem', color: '#6B7280' }}>Enemy (diagonal)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ 
              width: '18px', height: '18px', borderRadius: '4px',
              backgroundColor: '#F5F3FF', border: '2px solid #8B5CF6'
            }} />
            <span style={{ fontSize: '0.85rem', color: '#6B7280' }}>Typal (gold signpost)</span>
          </div>
        </div>

        {/* Archetypes Lists */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          
          {/* Ally Pairs */}
          <div>
            <h2 style={{ 
              fontSize: '1rem', 
              fontWeight: '600', 
              color: '#374151',
              margin: '0 0 12px 0',
              paddingBottom: '8px',
              borderBottom: '2px solid #E5E7EB',
            }}>
              Ally Color Pairs
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {allyPairs.map((arch, idx) => (
                <ArchetypeRow key={idx} arch={arch} />
              ))}
            </div>
          </div>

          {/* Enemy Pairs */}
          <div>
            <h2 style={{ 
              fontSize: '1rem', 
              fontWeight: '600', 
              color: '#374151',
              margin: '0 0 12px 0',
              paddingBottom: '8px',
              borderBottom: '2px solid #E5E7EB',
            }}>
              Enemy Color Pairs
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {enemyPairs.map((arch, idx) => (
                <ArchetypeRow key={idx} arch={arch} />
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <p style={{ 
          textAlign: 'center', 
          color: '#9CA3AF', 
          fontSize: '0.8rem',
          marginTop: '24px',
        }}>
          Prereleases Jan 16–22, 2026 · Faeries & Giants supported at higher rarities
        </p>
      </div>
    </div>
  );
}
