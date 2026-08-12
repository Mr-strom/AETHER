import React, { useEffect } from 'react';
import { useStore } from '../stores/useStore';
import { fetchSystemStatus } from '../api/client';
import { Cpu, HardDrive, ShieldCheck, Activity } from 'lucide-react';

export const SystemStatusComponent: React.FC = () => {
  const { systemStatus, setSystemStatus } = useStore();

  useEffect(() => {
    fetchSystemStatus()
      .then(setSystemStatus)
      .catch(() => {
        // Fallback default
        setSystemStatus({
          status: 'ok',
          version: '1.0.0',
          models_loaded: [],
          ram_budget_mb: 14336,
          ram_usage_mb: 0,
          gpu_layers: 999,
          gpu_available: false,
          active_sources_count: 0,
          total_evidence_chunks: 0,
        });
      });
  }, [setSystemStatus]);

  if (!systemStatus) return null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs space-y-2 text-slate-300">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2 font-medium">
        <span className="flex items-center gap-1.5 text-cyan-400">
          <Activity className="w-4 h-4" /> System Health
        </span>
        <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
          {systemStatus.status.toUpperCase()} v{systemStatus.version}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 pt-1">
        <div className="flex items-center gap-1.5">
          <HardDrive className="w-3.5 h-3.5 text-slate-400" />
          <span>RAM: {systemStatus.ram_usage_mb} / {systemStatus.ram_budget_mb} MB</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5 text-slate-400" />
          <span>GPU Layers: {systemStatus.gpu_layers}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
          <span>Models: {systemStatus.models_loaded.length} Loaded</span>
        </div>
      </div>
    </div>
  );
};
