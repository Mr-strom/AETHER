import React, { useEffect, useState } from 'react';
import { Menu, Shield, Settings } from 'lucide-react';
import { AetherBrand } from './AetherLogo';
import { verifyAirgap } from '../api/client';

interface TopBarProps {
  onToggleSidebar: () => void;
  lastQueryTime: string | null;
}

const TopBar: React.FC<TopBarProps> = ({ onToggleSidebar, lastQueryTime }) => {
  const [airgapGreen, setAirgapGreen] = useState<boolean | null>(null);

  useEffect(() => {
    verifyAirgap()
      .then((r) => setAirgapGreen(r.all_green))
      .catch(() => setAirgapGreen(null));
  }, []);

  return (
    <header className="h-topbar w-full bg-aether-bg border-b border-aether-border flex items-center px-4 shrink-0 z-30">
      {/* Left: Hamburger + Brand */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-lg hover:bg-aether-hover transition-colors text-gray-400 hover:text-gray-200"
        >
          <Menu size={18} />
        </button>
        <AetherBrand iconSize={24} />
      </div>

      {/* Right section */}
      <div className="ml-auto flex items-center gap-4">
        {lastQueryTime && (
          <span className="text-xs text-neutral font-mono hidden sm:block">
            Last Query: {lastQueryTime}
          </span>
        )}

        {/* Airgap shield */}
        <div
          className="relative cursor-pointer"
          title={
            airgapGreen === null
              ? 'Airgap: checking...'
              : airgapGreen
              ? 'Airgap: VERIFIED OFFLINE'
              : 'Airgap: NOT VERIFIED'
          }
        >
          <Shield
            size={18}
            className={
              airgapGreen === null
                ? 'text-neutral'
                : airgapGreen
                ? 'text-accent-green'
                : 'text-accent-red'
            }
          />
          {airgapGreen && (
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-accent-green rounded-full" />
          )}
        </div>

        <button className="p-1.5 rounded-lg hover:bg-aether-hover transition-colors text-gray-400 hover:text-gray-200">
          <Settings size={18} />
        </button>
      </div>
    </header>
  );
};

export default TopBar;
