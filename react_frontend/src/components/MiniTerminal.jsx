import React, { useEffect, useState, useCallback } from 'react';
import CommandCenterMap from './CommandCenterMap';

const STATUS_ICONS = {
  online: '🟢',
  offline: '🔴',
  connecting: '🟡',
};

export default function MiniTerminal() {
  const [tg, setTg] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [agentCount, setAgentCount] = useState(0);

  useEffect(() => {
    if (window.Telegram?.WebApp) {
      const webapp = window.Telegram.WebApp;
      webapp.ready();
      webapp.expand();
      if (typeof webapp.enableClosingConfirmation === 'function') {
        webapp.enableClosingConfirmation();
      }
      webapp.MainButton.setText('TACTICAL OVERLAY');
      webapp.MainButton.show();
      webapp.MainButton.onClick(() => {
        webapp.showAlert('Tactical mode activated');
      });
      setTg(webapp);
    }
    setConnectionStatus('online');

    const interval = setInterval(() => {
      setLastUpdate(new Date().toLocaleTimeString('en-US', { hour12: false }));
      setAgentCount((prev) => prev + Math.floor(Math.random() * 2));
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const handleClose = useCallback(() => {
    if (tg) {
      tg.showConfirm('Закрыть терминал?', (confirmed) => {
        if (confirmed) tg.close();
      });
    }
  }, [tg]);

  const themeColors = {
    bg: tg?.themeParams?.bg_color || '#000',
    text: tg?.themeParams?.text_color || '#fff',
    hint: tg?.themeParams?.hint_color || '#999',
    accent: tg?.themeParams?.button_color || '#00ffcc',
  };

  return (
    <div
      className="w-full h-screen overflow-hidden relative"
      style={{ backgroundColor: themeColors.bg, color: themeColors.text }}
    >
      <CommandCenterMap isMobile />

      {/* ═══ HUD Overlay ═══ */}
      <div className="absolute top-3 left-3 right-3 z-10 flex justify-between items-start pointer-events-none">
        {/* Agent Badge */}
        <div
          className="bg-black/80 p-3 rounded-lg border border-cyan-500/50 backdrop-blur-md pointer-events-auto"
          style={{ borderColor: `${themeColors.accent}66` }}
        >
          <h1
            className="font-mono text-sm uppercase tracking-widest font-bold"
            style={{ color: themeColors.accent }}
          >
            {tg?.initDataUnsafe?.user?.username
              ? `AGENT: ${tg.initDataUnsafe.user.username}`
              : 'GHOST PROTOCOL'}
          </h1>
          <div className="text-xs font-mono mt-1 opacity-70" style={{ color: themeColors.hint }}>
            {STATUS_ICONS[connectionStatus]} LIVE TELEMETRY • 5Hz
          </div>
        </div>

        {/* Close Button */}
        {tg && (
          <button
            onClick={handleClose}
            className="bg-red-600/80 hover:bg-red-500 text-white px-3 py-2 rounded-lg text-sm font-mono pointer-events-auto transition-colors"
            type="button"
          >
            ✕
          </button>
        )}
      </div>

      {/* ═══ Status Bar ═══ */}
      <div className="absolute bottom-0 left-0 right-0 z-10 bg-black/90 backdrop-blur-md border-t border-cyan-500/30 px-4 py-2 flex justify-between items-center font-mono text-xs">
        <span style={{ color: themeColors.accent }}>
          NODES: {agentCount}
        </span>
        <span style={{ color: themeColors.hint }}>
          {lastUpdate || '--:--:--'} UTC
        </span>
        <span style={{ color: connectionStatus === 'online' ? '#00ff88' : '#ff4444' }}>
          {connectionStatus.toUpperCase()}
        </span>
      </div>
    </div>
  );
}
