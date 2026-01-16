import React from 'react';

const MTGColors = {
  W: { name: 'White', bg: '#F9FAF4', accent: '#F8E7B9', symbol: '☀️' },
  U: { name: 'Blue', bg: '#0E68AB', accent: '#AAE0FA', symbol: '💧' },
  B: { name: 'Black', bg: '#393B3A', accent: '#C9C5C2', symbol: '💀' },
  R: { name: 'Red', bg: '#D32029', accent: '#F9AA8F', symbol: '🔥' },
  G: { name: 'Green', bg: '#00733E', accent: '#9BD3AE', symbol: '🌲' },
};

const typalArchetypes = [
  { colors: ['W', 'U'], name: 'Azorius', tribe: '🧜 Merfolk', theme: 'Tap Triggers & Convoke', desc: 'Tap Merfolk for value; convoke spells trigger abilities without attacking', hasSignpost: true },
  { colors: ['B', 'R'], name: 'Rakdos', tribe: '👺 Goblins', theme: 'Blight & Sacrifice', desc: 'Put -1/-1 counters on your creatures for powerful effects; death triggers', hasSignpost: true },
  { colors: ['G', 'W'], name: 'Selesnya', tribe: '🏠 Kithkin', theme: 'Go-Wide Tokens', desc: 'Swarm the board with small creatures and overwhelm opponents', hasSignpost: true },
  { colors: ['B', 'G'], name: 'Golgari', tribe: '🧝 Elves', theme: 'Graveyard & Recursion', desc: 'Classic Lorwyn black-green elves with death and rebirth synergies', hasSignpost: true },
  { colors: ['U', 'R'], name: 'Izzet', tribe: '🔥 Elementals', theme: 'Big Spells (4+ MV)', desc: 'Cast expensive spells for powerful elemental triggers and payoffs', hasSignpost: true },
];

const mechanicalArchetypes = [
  { colors: ['U', 'B'], name: 'Dimir', theme: 'Flash & Trickery', desc: 'Play at instant speed; Faeries support the theme but not the focus', hasSignpost: false },
  { colors: ['W', 'B'], name: 'Orzhov', theme: 'Persist & Recursion', desc: '-1/-1 counters meet creatures that return from the grave', hasSignpost: false },
  { colors: ['R', 'W'], name: 'Boros', theme: 'Giants & Aggro', desc: 'Large creatures with aggressive strategies', hasSignpost: false },
  { colors: ['R', 'G'], name: 'Gruul', theme: 'Vivid & Power', desc: 'Color-matters abilities with big creature beatdown', hasSignpost: false },
  { colors: ['G', 'U'], name: 'Simic', theme: 'Vivid & Ramp', desc: 'Multi-color permanents fuel vivid payoffs; ramp into bombs', hasSignpost: false },
];

function ArchetypeCard({ arch, isPrimary }) {
  return (
    <div style={{
      background: isPrimary 
        ? 'linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(59,130,246,0.1) 100%)'
        : 'rgba(255,255,255,0.03)',
      borderRadius: '12px',
      padding: '14px',
      border: isPrimary 
        ? '1px solid rgba(139,92,246,0.3)' 
        : '1px solid rgba(255,255,255,0.08)',
      position: 'relative',
    }}>
      {isPrimary && (
        <div style={{
          position: 'absolute',
          top: '-8px',
          right: '12px',
          background: 'linear-gradient(90deg, #8B5CF6, #6366F1)',
          color: '#fff',
          padding: '2px 10px',
          borderRadius: '10px',
          fontSize: '0.7rem',
          fontWeight: 'bold',
        }}>
          TYPAL
        </div>
      )}
      
      <div style={{ display: 'flex', gap: '8px', marginBottom: '10px', alignItems: 'center' }}>
        {arch.colors.map((c, i) => (
          <div key={i} style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: MTGColors[c].bg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1rem',
            border: `2px solid ${MTGColors[c].accent}`,
            boxShadow: '0 2px 6px rgba(0,0,0,0.3)'
          }}>
            {MTGColors[c].symbol}
          </div>
        ))}
        {isPrimary && arch.tribe && (
          <span style={{ 
            marginLeft: '8px', 
            fontSize: '1.1rem',
            filter: 'grayscale(0)'
          }}>
            {arch.tribe.split(' ')[0]}
          </span>
        )}
      </div>
      
      <div style={{ 
        color: '#94a3b8', 
        fontSize: '0.75rem',
        marginBottom: '2px',
      }}>
        {arch.colors.map(c => MTGColors[c].name).join('-')} • {arch.name}
      </div>
      
      {isPrimary && arch.tribe && (
        <div style={{ 
          color: '#c4b5fd', 
          fontSize: '0.85rem',
          fontWeight: '600',
          marginBottom: '4px',
        }}>
          {arch.tribe.split(' ').slice(1).join(' ')}
        </div>
      )}
      
      <h3 style={{ 
        color: '#fff', 
        margin: '0 0 6px 0',
        fontSize: '1rem',
        fontWeight: '600'
      }}>
        {arch.theme}
      </h3>
      
      <p style={{ 
        color: '#64748b', 
        margin: 0,
        fontSize: '0.8rem',
        lineHeight: 1.4
      }}>
        {arch.desc}
      </p>
    </div>
  );
}

export default function LorwynEclipsedArchetypes() {
  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(145deg, #0f172a 0%, #1e1b4b 50%, #172554 100%)',
      padding: '20px',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <div style={{ maxWidth: '950px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{ 
            display: 'inline-flex', 
            gap: '8px', 
            marginBottom: '8px',
            padding: '6px 16px',
            background: 'rgba(255,255,255,0.05)',
            borderRadius: '20px'
          }}>
            <span>☀️</span>
            <span style={{ color: '#94a3b8' }}>Lorwyn</span>
            <span style={{ color: '#475569' }}>|</span>
            <span style={{ color: '#64748b' }}>Shadowmoor</span>
            <span>🌙</span>
          </div>
          <h1 style={{ 
            color: '#fff', 
            fontSize: '2rem', 
            margin: '8px 0',
            background: 'linear-gradient(90deg, #fff, #c4b5fd)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            Lorwyn Eclipsed
          </h1>
          <p style={{ color: '#64748b', margin: 0 }}>
            Draft Archetypes • Releases January 23, 2026
          </p>
        </div>

        {/* Primary Typal Archetypes */}
        <div style={{ marginBottom: '20px' }}>
          <h2 style={{ 
            color: '#c4b5fd', 
            fontSize: '1rem', 
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span style={{ 
              width: '24px', 
              height: '24px', 
              background: 'linear-gradient(90deg, #8B5CF6, #6366F1)',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.8rem'
            }}>★</span>
            Primary Archetypes — Creature Types (Gold Signpost Uncommons)
          </h2>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '12px'
          }}>
            {typalArchetypes.map((arch, idx) => (
              <ArchetypeCard key={idx} arch={arch} isPrimary={true} />
            ))}
          </div>
        </div>

        {/* Secondary Mechanical Archetypes */}
        <div style={{ marginBottom: '20px' }}>
          <h2 style={{ 
            color: '#64748b', 
            fontSize: '1rem', 
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span style={{ 
              width: '24px', 
              height: '24px', 
              background: 'rgba(255,255,255,0.1)',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.8rem'
            }}>○</span>
            Secondary Archetypes — Mechanical Themes (Hybrid Uncommons Only)
          </h2>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '12px'
          }}>
            {mechanicalArchetypes.map((arch, idx) => (
              <ArchetypeCard key={idx} arch={arch} isPrimary={false} />
            ))}
          </div>
        </div>

        {/* Key Mechanics */}
        <div style={{
          background: 'rgba(255,255,255,0.03)',
          borderRadius: '12px',
          padding: '16px',
          border: '1px solid rgba(255,255,255,0.08)'
        }}>
          <h3 style={{ color: '#fff', margin: '0 0 12px 0', fontSize: '0.95rem' }}>
            Key Set Mechanics
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {[
              { name: 'Blight', desc: 'Put -1/-1 counters on your creatures as a cost', color: '#a78bfa' },
              { name: 'Vivid', desc: 'Abilities scale with # of colors among your permanents', color: '#60a5fa' },
              { name: 'Kindred', desc: 'Noncreature cards with creature types (Tribal)', color: '#34d399' },
              { name: 'Changeling', desc: 'Creature is every creature type', color: '#fbbf24' },
              { name: 'Convoke', desc: 'Tap creatures to help pay for spells', color: '#f472b6' },
              { name: 'DFCs', desc: 'Double-faced cards: Lorwyn ↔ Shadowmoor', color: '#94a3b8' },
            ].map((mech, i) => (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.05)',
                padding: '6px 12px',
                borderRadius: '8px',
                flex: '1 1 180px',
                borderLeft: `3px solid ${mech.color}`
              }}>
                <span style={{ color: mech.color, fontWeight: '600', fontSize: '0.85rem' }}>{mech.name}</span>
                <span style={{ color: '#64748b', marginLeft: '6px', fontSize: '0.75rem' }}>{mech.desc}</span>
              </div>
            ))}
          </div>
        </div>
        
        <p style={{ 
          textAlign: 'center', 
          color: '#475569', 
          marginTop: '16px',
          fontSize: '0.75rem'
        }}>
          Prereleases: January 16–22 • Faeries & Giants supported at higher rarities
        </p>
      </div>
    </div>
  );
}
