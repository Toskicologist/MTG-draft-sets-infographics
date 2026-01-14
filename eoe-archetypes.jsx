import React from 'react';

const MTGColors = {
  W: { name: 'White', bg: '#F9FAF4', accent: '#F8E7B9', symbol: '☀️' },
  U: { name: 'Blue', bg: '#0E68AB', accent: '#AAE0FA', symbol: '💧' },
  B: { name: 'Black', bg: '#393B3A', accent: '#C9C5C2', symbol: '💀' },
  R: { name: 'Red', bg: '#D32029', accent: '#F9AA8F', symbol: '🔥' },
  G: { name: 'Green', bg: '#00733E', accent: '#9BD3AE', symbol: '🌲' },
};

const archetypes = [
  { colors: ['W', 'U'], name: 'Azorius', theme: 'Second Spell Tempo', desc: 'Cast 2+ spells per turn for value triggers', tier: 'S' },
  { colors: ['U', 'B'], name: 'Dimir', theme: 'Artifact Control', desc: 'Grind opponents with artifact synergies', tier: 'A' },
  { colors: ['B', 'R'], name: 'Rakdos', theme: 'Void Aggro', desc: 'Trigger void when permanents leave play', tier: 'A' },
  { colors: ['R', 'G'], name: 'Gruul', theme: 'Landfall', desc: 'Trigger bonuses when lands enter', tier: 'A' },
  { colors: ['G', 'W'], name: 'Selesnya', theme: '+1/+1 Counters', desc: 'Grow creatures with counter synergies', tier: 'B' },
  { colors: ['W', 'B'], name: 'Orzhov', theme: 'Sacrifice Value', desc: 'Trade creatures for incremental advantage', tier: 'C' },
  { colors: ['U', 'R'], name: 'Izzet', theme: 'Artifact Aggro', desc: 'Pump creatures by playing artifacts', tier: 'B' },
  { colors: ['B', 'G'], name: 'Golgari', theme: 'Graveyard Recursion', desc: 'Mill and reanimate key pieces', tier: 'C' },
  { colors: ['R', 'W'], name: 'Boros', theme: 'Spacecraft & Tapped', desc: 'Station spacecraft with tapped creatures', tier: 'C' },
  { colors: ['G', 'U'], name: 'Simic', theme: 'Lander Ramp', desc: 'Ramp with Landers, splash bombs', tier: 'S' },
];

const tierColors = {
  S: { bg: '#FFD700', text: '#000' },
  A: { bg: '#4CAF50', text: '#fff' },
  B: { bg: '#2196F3', text: '#fff' },
  C: { bg: '#9E9E9E', text: '#fff' },
};

export default function EOEArchetypes() {
  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
      padding: '24px',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        <h1 style={{ 
          textAlign: 'center', 
          color: '#fff', 
          fontSize: '2rem', 
          marginBottom: '8px',
          textShadow: '0 2px 10px rgba(0,0,0,0.5)'
        }}>
          Edge of Eternities
        </h1>
        <p style={{ 
          textAlign: 'center', 
          color: '#94a3b8', 
          marginBottom: '24px',
          fontSize: '1.1rem'
        }}>
          Draft Archetypes by Color Pair
        </p>
        
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '16px'
        }}>
          {archetypes.map((arch, idx) => (
            <div key={idx} style={{
              background: 'rgba(255,255,255,0.05)',
              borderRadius: '12px',
              padding: '16px',
              border: '1px solid rgba(255,255,255,0.1)',
              backdropFilter: 'blur(10px)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{
                position: 'absolute',
                top: '8px',
                right: '8px',
                background: tierColors[arch.tier].bg,
                color: tierColors[arch.tier].text,
                padding: '2px 10px',
                borderRadius: '12px',
                fontSize: '0.75rem',
                fontWeight: 'bold'
              }}>
                Tier {arch.tier}
              </div>
              
              <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                {arch.colors.map((c, i) => (
                  <div key={i} style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '50%',
                    background: MTGColors[c].bg,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.2rem',
                    border: `3px solid ${MTGColors[c].accent}`,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
                  }}>
                    {MTGColors[c].symbol}
                  </div>
                ))}
              </div>
              
              <div style={{ 
                color: '#e2e8f0', 
                fontSize: '0.85rem',
                marginBottom: '4px',
                opacity: 0.7
              }}>
                {arch.colors.map(c => MTGColors[c].name).join(' / ')} • {arch.name}
              </div>
              
              <h3 style={{ 
                color: '#fff', 
                margin: '0 0 8px 0',
                fontSize: '1.1rem'
              }}>
                {arch.theme}
              </h3>
              
              <p style={{ 
                color: '#94a3b8', 
                margin: 0,
                fontSize: '0.9rem',
                lineHeight: 1.4
              }}>
                {arch.desc}
              </p>
            </div>
          ))}
        </div>
        
        <div style={{
          marginTop: '24px',
          padding: '16px',
          background: 'rgba(255,255,255,0.05)',
          borderRadius: '12px',
          border: '1px solid rgba(255,255,255,0.1)'
        }}>
          <h3 style={{ color: '#fff', margin: '0 0 12px 0', fontSize: '1rem' }}>Key Set Mechanics</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
            {[
              { name: 'Spacecraft', desc: 'Artifacts that become creatures with charge counters' },
              { name: 'Station', desc: 'Tap creatures to add charge counters = their power' },
              { name: 'Warp', desc: 'Alternate cast cost for spells' },
              { name: 'Void', desc: 'Triggers when permanents leave the battlefield' },
              { name: 'Landers', desc: 'Artifact tokens that fetch basic lands' },
            ].map((mech, i) => (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.08)',
                padding: '8px 12px',
                borderRadius: '8px',
                flex: '1 1 200px'
              }}>
                <span style={{ color: '#fbbf24', fontWeight: 'bold' }}>{mech.name}:</span>
                <span style={{ color: '#94a3b8', marginLeft: '6px' }}>{mech.desc}</span>
              </div>
            ))}
          </div>
        </div>
        
        <p style={{ 
          textAlign: 'center', 
          color: '#64748b', 
          marginTop: '20px',
          fontSize: '0.8rem'
        }}>
          Tier rankings based on early format data • Green is the strongest color, Red is weakest
        </p>
      </div>
    </div>
  );
}
