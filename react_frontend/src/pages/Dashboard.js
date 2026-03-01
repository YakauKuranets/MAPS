import React, { useState, useMemo } from 'react';
import DashboardLayout from '../components/DashboardLayout';
import CommandCenterMap from '../components/CommandCenterMap';
import IncidentFeed from '../components/IncidentFeed';
import VideoModal from '../components/VideoModal';
import ObjectInspector from '../components/ObjectInspector';
import IncidentChat from '../components/IncidentChat';
import IncidentChatPanel from '../components/IncidentChatPanel';
import PendingRequestsPanel from '../components/PendingRequestsPanel';
import SmartFilterPanel from '../components/SmartFilterPanel';
import CyberHUD from '../components/CyberHUD';
import AssetRiskGraphPanel from '../components/AssetRiskGraphPanel';
import IdentityGraphPanel from '../components/IdentityGraphPanel';
import useMapStore from '../store/useMapStore';

const mockData = {
  alias: 'apt-ghost',
  connections: [
    { entity: 'bc1q7x...f93k', type: 'CRYPTO_WALLET', relation: 'RECEIVED_FUNDS' },
    { entity: 'UTC+3 (based on activity hours and slang)', type: 'TIMEZONE', relation: 'OPERATES_IN' },
    { entity: '0xDEADBEEF_PGP', type: 'PGP_KEY', relation: 'SIGNED_WITH' },
  ],
};

export default function Dashboard() {
  const [activeObjectId, setActiveObjectId] = useState(null);
  const [activeNode, setActiveNode] = useState(null);
  const [activeTab, setActiveTab] = useState('radar');
  const [theme, setTheme] = useState('dark');
  const [flyToTarget, setFlyToTarget] = useState(null);
  const [activeChatIncidentId, setActiveChatIncidentId] = useState(null);
  const [assetRiskData] = useState({ nodes: [], edges: [] });
  const [filters, setFilters] = useState({
    showAgents: true,
    showCameras: true,
    showIncidents: true,
    showPending: true,
  });

  const trackers = useMapStore((s) => s.trackers);

  const selectedObjectData = useMemo(() => {
    if (!activeObjectId || !trackers[activeObjectId]) return null;
    return { id: activeObjectId, ...trackers[activeObjectId] };
  }, [activeObjectId, trackers]);

  const bgClass = theme === 'dark' ? 'bg-slate-950' : 'bg-slate-100';

  const renderContent = () => {
    switch (activeTab) {
      case 'radar':
        return (
          <>
            {/* center map stage with gutters */}
            <div className="absolute inset-0">
              <div className="absolute inset-0 left-64 right-[390px] top-16 bottom-0">
                <CommandCenterMap
                  theme={theme}
                  flyToTarget={flyToTarget}
                  onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                  onUserClick={(id) => setActiveObjectId(id)}
                  setActiveNode={setActiveNode}
                  filters={filters}
                />
              </div>
            </div>

            {/* right stack */}
            <div className="absolute right-4 top-20 bottom-4 z-40 w-[370px] space-y-3 pointer-events-none">
              <div className="pointer-events-auto">
                <IdentityGraphPanel actorData={mockData} />
              </div>
            </div>

            {/* utility overlays, moved away from left rail/right stack collisions */}
            <div className="absolute left-64 top-20 z-40 pointer-events-auto">
              <PendingRequestsPanel onFlyToPending={setFlyToTarget} />
            </div>

            <div className="absolute right-[390px] top-20 z-40 pointer-events-auto">
              <SmartFilterPanel filters={filters} onFiltersChange={setFilters} />
            </div>

            <div className="absolute left-64 right-[390px] top-20 z-30 pointer-events-none">
              <IncidentFeed theme={theme} />
            </div>

            <IncidentChat />
          </>
        );
      case 'agents':
        return (
          <div className={`p-10 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
            Раздел списка сотрудников (в разработке)
          </div>
        );
      case 'analytics':
        return (
          <div className="p-6">
            <h2 className={`mb-4 font-mono text-sm ${theme === 'dark' ? 'text-cyan-300' : 'text-slate-700'}`}>
              ASSET RISK GRAPH
            </h2>
            <AssetRiskGraphPanel riskData={assetRiskData} />
          </div>
        );
      case 'settings':
        return (
          <div className={`p-10 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
            Раздел настроек (в разработке)
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <DashboardLayout activeTab={activeTab} onTabChange={setActiveTab}>
      <div className={`relative h-full w-full transition-colors duration-500 ${bgClass}`}>
        {renderContent()}

        {activeChatIncidentId !== null && (
          <IncidentChatPanel
            incidentId={activeChatIncidentId}
            onClose={() => setActiveChatIncidentId(null)}
          />
        )}

        <ObjectInspector data={selectedObjectData} onClose={() => setActiveObjectId(null)} theme={theme} />
        <VideoModal userId={activeObjectId} onClose={() => setActiveObjectId(null)} theme={theme} />

        <CyberHUD
          activeNode={activeNode}
          setActiveNode={setActiveNode}
          theme={theme}
          activeTab={activeTab}
        />
      </div>
    </DashboardLayout>
  );
}
