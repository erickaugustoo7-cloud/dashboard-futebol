'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/',           icon: '📊', label: 'Sugestões do Dia',     section: 'análise' },
  { href: '/combinadas', icon: '🎫', label: 'Bilhetes Combinados',  section: 'análise' },
  { href: '/matches',    icon: '⚽', label: 'Todas as Partidas',    section: 'explorar' },
  { href: '/leagues',    icon: '🏆', label: 'Estatísticas por Liga',section: 'explorar' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="logo-icon">🎯</div>
        <div>
          <div className="logo-text">ScoutZin</div>
          <div className="logo-sub">AI Football Analytics</div>
        </div>
      </div>

      {/* Search */}
      <div className="sidebar-search">
        <span className="search-icon">🔍</span>
        <input type="text" placeholder="Buscar time ou liga..." className="search-input" />
      </div>

      {/* Navigation */}
      <div className="sidebar-section-label">Análise Diária</div>

      {NAV_ITEMS.filter(n => n.section === 'análise').map(item => (
        <Link
          key={item.href}
          href={item.href}
          className={`nav-item ${pathname === item.href ? 'active' : ''}`}
        >
          <span className="nav-icon">{item.icon}</span>
          {item.label}
        </Link>
      ))}

      <div className="sidebar-section-label" style={{ marginTop: '16px' }}>Explorar</div>

      {NAV_ITEMS.filter(n => n.section === 'explorar').map(item => (
        <Link
          key={item.href}
          href={item.href}
          className={`nav-item ${pathname === item.href ? 'active' : ''}`}
        >
          <span className="nav-icon">{item.icon}</span>
          {item.label}
        </Link>
      ))}

      {/* Footer spacer */}
      <div style={{ flex: 1 }} />

      {/* Info footer */}
      <div style={{
        padding: '12px 14px',
        borderTop: '1px solid var(--border)',
        marginTop: '16px',
      }}>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>Motor</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {[
            { label: 'Poisson', color: 'var(--accent)' },
            { label: 'ELO Rating', color: '#8b5cf6' },
            { label: 'Form Recente', color: 'var(--medium)' },
            { label: 'H2H Context', color: 'var(--high)' },
          ].map(m => (
            <div key={m.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: m.color, flexShrink: 0 }} />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{m.label}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
