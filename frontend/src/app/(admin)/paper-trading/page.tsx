"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import Button from "@/components/ui/button/Button";
import Badge from "@/components/ui/badge/Badge";
import { ArrowUpIcon, ArrowDownIcon } from "@/icons";

const BE = "/api/backend";

const getWebSocketUrl = () => {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
  return backendUrl.replace("http", "ws") + "/paper-trading/ws/sessions";
};

type AccountInfo = {
  id: string;
  alias: string;
  currency: string;
  balance: number;
  unrealized_pl: number;
  nav: number;
  margin_used: number;
  margin_available: number;
  position_value: number;
  open_trade_count: number;
  open_position_count: number;
};

type PaperSession = {
  session_id: string;
  account_id: string;
  strategy_name: string;
  strategy_params: Record<string, unknown>;
  instrument: string;
  granularity: string;
  status: string;
  initial_balance: number;
  current_balance: number;
  equity: number;
  unrealized_pl: number;
  realized_pl: number;
  margin_used: number;
  margin_available: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  positions: Record<string, unknown>;
  open_trades_count: number;
  closed_trades_count: number;
  start_time: string | null;
  last_update: string | null;
  error_message: string | null;
  max_position_size: number;
  max_daily_loss: number;
  daily_loss: number;
};

type Strategy = {
  key: string;
  doc?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  params_schema?: Record<string, unknown>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  presets?: Record<string, unknown> | null;
};

type Position = {
  instrument: string;
  units: number;
  avg_price: number;
  unrealized_pl: number;
};

type Trade = {
  id: string;
  instrument: string;
  open_time: string | null;
  close_time: string | null;
  open_price: number;
  close_price: number | null;
  units: number;
  realized_pl: number;
};

function StatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, "primary" | "success" | "error" | "warning" | "info" | "light" | "dark"> = {
    running: "success",
    stopped: "error",
    paused: "warning",
    error: "error",
    starting: "info",
    stopping: "warning",
  };
  
  return (
    <Badge color={colorMap[status] || "light"} variant="solid" size="sm">
      {status.toUpperCase()}
    </Badge>
  );
}

function ConnectionStatus({ isConnected, lastUpdateTime }: { isConnected: boolean; lastUpdateTime: number }) {
  const [timeSinceUpdate, setTimeSinceUpdate] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => {
      setTimeSinceUpdate(Math.floor((Date.now() - lastUpdateTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [lastUpdateTime]);
  
  return (
    <div className="mb-4 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-success animate-pulse' : 'bg-warning'}`}></div>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {isConnected ? 'Connected' : 'Disconnected'} • Last update: {timeSinceUpdate}s ago
        </span>
      </div>
    </div>
  );
}

function SessionCard({
  session,
  positions,
  trades,
  onStartSession,
  onStopSession,
  onPauseSession,
  onResumeSession,
  onDeleteSession,
}: {
  session: PaperSession;
  positions: Position[];
  trades: { open: Trade[]; closed: Trade[] };
  onStartSession: (sessionId: string) => void;
  onStopSession: (sessionId: string) => void;
  onPauseSession: (sessionId: string) => void;
  onResumeSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const closedTrades = trades?.closed || [];
  const openTrades = trades?.open || [];
  const winRate = session.total_trades > 0
    ? ((session.winning_trades / session.total_trades) * 100).toFixed(1)
    : "0.0";
  
  const isRunning = session.status === "running";
  const isPaused = session.status === "paused";
  const isStopped = session.status === "stopped";
  const isStarting = session.status === "starting";
  const isStopping = session.status === "stopping";
  const primaryLabel = isStarting
    ? "Starting..."
    : isStopping
    ? "Stopping..."
    : isRunning
    ? "Pause Strategy"
    : isPaused
    ? "Resume Strategy"
    : "Start Strategy";
  const stopLabel = isStopping ? "Stopping..." : "Stop & Close Positions";
  const handlePrimaryClick = () => {
    if (isStarting || isStopping) return;
    if (isRunning) {
      onPauseSession(session.session_id);
    } else if (isPaused) {
      onResumeSession(session.session_id);
    } else {
      onStartSession(session.session_id);
    }
  };
  const handleStopClick = () => {
    if (isStopping || isStarting || isStopped) return;
    onStopSession(session.session_id);
  };
  
  return (
    <div className="p-5 rounded-xl border border-stroke dark:border-strokedark bg-gray-50 dark:bg-gray-900 hover:border-primary dark:hover:border-primary transition-colors">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div 
            className="flex items-center gap-3 mb-2 cursor-pointer"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            <h4 className="text-lg font-semibold text-gray-800 dark:text-white/90">
              {session.strategy_name}
            </h4>
            <StatusBadge status={session.status} />
            <svg
              className={`w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {session.instrument} • {session.granularity}
          </p>
        </div>
        
        <div className="flex flex-wrap gap-2">
          <Button
            variant={isRunning ? "outline" : "primary"}
            size="sm"
            onClick={handlePrimaryClick}
            disabled={isStarting || isStopping}
          >
            {primaryLabel}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleStopClick}
            disabled={isStopped || isStarting || isStopping}
          >
            {stopLabel}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-error-500 hover:text-error-600"
            onClick={() => onDeleteSession(session.session_id)}
          >
            Delete Session
          </Button>
        </div>
      </div>
      
      {session.error_message && (
        <div className="mb-4 p-3 rounded-lg bg-error/10 dark:bg-error/20 border border-error">
          <p className="text-sm text-error">{session.error_message}</p>
        </div>
      )}
      
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Balance</p>
          <p className="text-sm font-semibold text-gray-800 dark:text-white/90">
            ${session.current_balance.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Realized P&L</p>
          <p className={`text-sm font-semibold ${session.realized_pl >= 0 ? 'text-success-500 dark:text-success-400' : 'text-error-500 dark:text-error-400'}`}>
            {session.realized_pl >= 0 ? '+' : ''}{session.realized_pl.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Unrealized P&L</p>
          <p className={`text-sm font-semibold ${session.unrealized_pl >= 0 ? 'text-success-500 dark:text-success-400' : 'text-error-500 dark:text-error-400'}`}>
            {session.unrealized_pl >= 0 ? '+' : ''}{session.unrealized_pl.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Trades / Win Rate</p>
          <p className="text-sm font-semibold text-gray-800 dark:text-white/90">
            {session.total_trades} / {winRate}%
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Positions</p>
          <p className="text-sm font-semibold text-gray-800 dark:text-white/90">
            {positions.length}
          </p>
        </div>
      </div>
      
      {positions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-stroke dark:border-strokedark">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Open Positions</p>
          <div className="space-y-2">
            {positions.map((pos, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-white dark:bg-gray-900">
                <div>
                  <p className="text-sm font-medium text-gray-800 dark:text-white/90">{pos.instrument}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {pos.units > 0 ? 'LONG' : 'SHORT'} {Math.abs(pos.units).toFixed(0)} @ {pos.avg_price.toFixed(5)}
                  </p>
                </div>
                <p className={`text-sm font-semibold ${pos.unrealized_pl >= 0 ? 'text-success-500 dark:text-success-400' : 'text-error-500 dark:text-error-400'}`}>
                  {pos.unrealized_pl >= 0 ? '+' : ''}{pos.unrealized_pl.toFixed(2)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-stroke dark:border-strokedark space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-white dark:bg-gray-800">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Trades</p>
              <p className="text-lg font-bold text-gray-800 dark:text-white/90">
                {closedTrades.length + openTrades.length}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {openTrades.length} open, {closedTrades.length} closed
              </p>
            </div>
            <div className="p-3 rounded-lg bg-white dark:bg-gray-800">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Win Rate</p>
              <p className="text-lg font-bold text-gray-800 dark:text-white/90">{winRate}%</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {session.winning_trades}W / {session.losing_trades}L
              </p>
            </div>
            <div className="p-3 rounded-lg bg-white dark:bg-gray-800">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Equity</p>
              <p className="text-lg font-bold text-gray-800 dark:text-white/90">
                ${session.equity.toFixed(2)}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-white dark:bg-gray-800">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Positions</p>
              <p className="text-lg font-bold text-gray-800 dark:text-white/90">
                {positions.length}
              </p>
            </div>
          </div>
          
          {(closedTrades.length > 0 || openTrades.length > 0) && (
            <div className="pt-2 border-t border-stroke dark:border-strokedark">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                Trade History ({closedTrades.length + openTrades.length})
              </p>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {[...closedTrades, ...openTrades].slice().reverse().map((trade) => {
                  const isClosed = trade.close_time !== null;
                  const isPositive = trade.realized_pl >= 0;
                  const openDate = trade.open_time ? new Date(trade.open_time) : null;
                  const closeDate = trade.close_time ? new Date(trade.close_time) : null;
                  
                  return (
                    <div key={trade.id} className="flex items-center justify-between p-2 rounded-lg bg-white dark:bg-gray-800 border border-stroke dark:border-strokedark">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm font-medium text-gray-800 dark:text-white/90">{trade.instrument}</p>
                          {isClosed ? (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">CLOSED</span>
                          ) : (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-success-100 dark:bg-success-500/20 text-success-600 dark:text-success-400">OPEN</span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {trade.units > 0 ? 'LONG' : 'SHORT'} {Math.abs(trade.units).toFixed(0)} @ {trade.open_price.toFixed(5)}
                          {isClosed && trade.close_price && ` → ${trade.close_price.toFixed(5)}`}
                        </p>
                        {openDate && (
                          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                            {openDate.toLocaleString()}
                            {closeDate && ` → ${closeDate.toLocaleString()}`}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        {isClosed ? (
                          <p className={`text-sm font-semibold ${isPositive ? 'text-success-500 dark:text-success-400' : 'text-error-500 dark:text-error-400'}`}>
                            {isPositive ? '+' : ''}{trade.realized_pl.toFixed(2)}
                          </p>
                        ) : (
                          <p className="text-sm font-semibold text-gray-500 dark:text-gray-400">Open</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AccountCard({ 
  account, 
  sessions,
  onClick 
}: { 
  account: AccountInfo;
  sessions: PaperSession[];
  onClick: () => void;
}) {
  const activeSession = sessions.find(s => s.account_id === account.id && s.status === "running");
  const allAccountSessions = sessions.filter(s => s.account_id === account.id);
  
  // Calculate total P&L from all sessions (realized + unrealized)
  const totalRealizedPL = allAccountSessions.reduce((sum, s) => sum + s.realized_pl, 0);
  const totalUnrealizedPL = allAccountSessions.reduce((sum, s) => sum + s.unrealized_pl, 0);
  const totalPL = totalRealizedPL + totalUnrealizedPL;
  
  // Calculate percentage based on initial balance or current balance
  const initialBalance = allAccountSessions.length > 0 
    ? allAccountSessions[0].initial_balance || account.balance 
    : account.balance;
  const plPercent = initialBalance > 0 ? ((totalPL / initialBalance) * 100).toFixed(2) : "0.00";
  const isPositive = totalPL >= 0;
  
  return (
    <div 
      onClick={onClick}
      className="group relative overflow-hidden rounded-xl border-2 border-stroke dark:border-strokedark bg-white dark:bg-gray-900 p-6 cursor-pointer transition-all duration-300 hover:shadow-xl hover:scale-[1.02] hover:border-primary dark:hover:border-primary"
    >
      {activeSession && (
        <div className="absolute top-4 right-4 flex items-center gap-2 px-3 py-1 rounded-full border border-success-500/40 bg-success-500/15 dark:bg-success-500/20">
          <div className="h-2 w-2 rounded-full bg-success-500 animate-pulse"></div>
          <span className="text-xs font-semibold tracking-wide text-success-600 dark:text-success-200">LIVE</span>
        </div>
      )}
      
      <div className="flex items-center gap-4 mb-6">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 dark:bg-primary/20 group-hover:bg-primary/20 transition-colors">
          <span className="text-2xl font-bold text-gray-800 dark:text-white">
            {account.alias?.charAt(0) || "A"}
          </span>
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-bold text-gray-800 dark:text-white/90 mb-1">
            {account.alias || "Account"}
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{account.id}</p>
        </div>
      </div>
      
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">Balance</p>
        <p className="text-3xl font-bold text-gray-800 dark:text-white/90">
          ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{account.currency}</p>
      </div>
      
      <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-gray-800">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total P&L</p>
          <p className={`text-lg font-bold ${isPositive ? 'text-success-500 dark:text-success-400' : 'text-error-500 dark:text-error-400'}`}>
            {isPositive ? '+' : ''}${totalPL.toFixed(2)}
          </p>
          {totalRealizedPL !== 0 && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Realized: {totalRealizedPL >= 0 ? '+' : ''}${totalRealizedPL.toFixed(2)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {isPositive ? (
            <ArrowUpIcon className={`w-5 h-5 ${isPositive ? 'text-success-500 dark:text-success-400' : 'text-error-500 dark:text-error-400'}`} />
          ) : (
            <ArrowDownIcon className={`w-5 h-5 ${isPositive ? 'text-success-500 dark:text-success-400' : 'text-error-500 dark:text-error-400'}`} />
          )}
          <span className={`text-xl font-bold ${isPositive ? 'text-success-500 dark:text-success-400' : 'text-error-500 dark:text-error-400'}`}>
            {plPercent}%
          </span>
        </div>
      </div>
      
      <div className="mt-4 pt-4 border-t border-stroke dark:border-strokedark grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Positions</p>
          <p className="text-sm font-semibold text-gray-800 dark:text-white/90">{account.open_position_count}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Open Trades</p>
          <p className="text-sm font-semibold text-gray-800 dark:text-white/90">{account.open_trade_count}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Sessions</p>
          <p className="text-sm font-semibold text-gray-800 dark:text-white/90">{allAccountSessions.length}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Active</p>
          <p className="text-sm font-semibold text-gray-800 dark:text-white/90">
            {allAccountSessions.filter(s => s.status === "running").length}
          </p>
        </div>
      </div>
      
      {activeSession && (
        <div className="mt-4 pt-4 border-t border-stroke dark:border-strokedark">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-success"></div>
            <p className="text-xs font-medium text-gray-800 dark:text-white/90">
              {activeSession.strategy_name}
            </p>
            <span className="text-xs text-gray-500 dark:text-gray-400">•</span>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {activeSession.instrument}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function AccountManagementModal({
  isOpen,
  onClose,
  account,
  sessions,
  strategies,
  onCreateSession,
  onStartSession,
  onStopSession,
  onPauseSession,
  onResumeSession,
  onDeleteSession,
  positions,
  trades,
}: {
  isOpen: boolean;
  onClose: () => void;
  account: AccountInfo | null;
  sessions: PaperSession[];
  strategies: Strategy[];
  onCreateSession: (data: Record<string, unknown>) => void;
  onStartSession: (sessionId: string) => void;
  onStopSession: (sessionId: string) => void;
  onPauseSession: (sessionId: string) => void;
  onResumeSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  positions: Record<string, Position[]>;
  trades: Record<string, { open: Trade[]; closed: Trade[] }>;
}) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({
    strategy_name: "",
    instrument: "EUR_USD",
    granularity: "M15",
    max_position_size: 10000,
    max_daily_loss: 1000,
  });
  const [selectedParams, setSelectedParams] = useState<Record<string, unknown>>({});
  const [selectedPreset, setSelectedPreset] = useState<string>("");
  
  const selectedStrategy = strategies.find(s => s.key === formData.strategy_name);
  
  useEffect(() => {
    if (selectedStrategy?.params_schema?.properties) {
      const defaults: Record<string, unknown> = {};
      Object.entries(selectedStrategy.params_schema.properties as Record<string, { default?: unknown }>).forEach(([key, schema]) => {
        if (schema.default !== undefined) {
          defaults[key] = schema.default;
        }
      });
      setSelectedParams(defaults);
      setSelectedPreset("");
    }
  }, [selectedStrategy]);
  
  useEffect(() => {
    if (selectedPreset && selectedStrategy?.presets?.[selectedPreset]) {
      setSelectedParams(selectedStrategy.presets[selectedPreset] as Record<string, unknown>);
    }
  }, [selectedPreset, selectedStrategy]);
  
  if (!isOpen || !account) return null;
  
  const accountSessions = sessions.filter(s => s.account_id === account.id);
  const plPercent = account.balance > 0 ? ((account.unrealized_pl / account.balance) * 100).toFixed(2) : "0.00";
  const isPositive = account.unrealized_pl >= 0;

  const handleCreateSession = () => {
    const session_id = `${account.alias}_${Date.now()}`;
    const sessionData: Record<string, unknown> = {
      session_id,
      account_id: account.id,
      strategy_name: formData.strategy_name,
      instrument: formData.instrument,
      granularity: formData.granularity,
      strategy_params: selectedParams,
      max_position_size: formData.max_position_size,
      max_daily_loss: formData.max_daily_loss,
    };
    
    onCreateSession(sessionData);
    setShowCreateForm(false);
    setFormData({
      strategy_name: "",
      instrument: "EUR_USD",
      granularity: "M15",
      max_position_size: 10000,
      max_daily_loss: 1000,
    });
  };
  
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 dark:bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border-2 border-gray-200 dark:border-gray-700 max-w-6xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 z-10 bg-white dark:bg-gray-900 border-b border-stroke dark:border-strokedark p-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 dark:bg-primary/20">
              <span className="text-xl font-bold text-gray-800 dark:text-white">
                {account.alias?.charAt(0) || "A"}
              </span>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-800 dark:text-white/90">
                {account.alias}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">{account.id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <svg className="w-6 h-6 text-gray-500 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl border border-stroke dark:border-strokedark bg-gray-50 dark:bg-gray-900">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Balance</p>
              <p className="text-2xl font-bold text-gray-800 dark:text-white/90">
                ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            
            <div className="p-4 rounded-xl border border-stroke dark:border-strokedark bg-gray-50 dark:bg-gray-900">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Equity</p>
              <p className="text-2xl font-bold text-gray-800 dark:text-white/90">
                ${account.nav.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            
            <div className="p-4 rounded-xl border border-stroke dark:border-strokedark bg-gray-50 dark:bg-gray-900">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Unrealized P&L</p>
              <p className={`text-2xl font-bold ${isPositive ? 'text-gray-800 dark:text-white' : 'text-gray-800 dark:text-white'}`}>
                {isPositive ? '+' : ''}{account.unrealized_pl.toFixed(2)}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{plPercent}%</p>
            </div>
            
            <div className="p-4 rounded-xl border border-stroke dark:border-strokedark bg-gray-50 dark:bg-gray-900">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Margin Available</p>
              <p className="text-2xl font-bold text-gray-800 dark:text-white/90">
                ${account.margin_available.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-gray-800 dark:text-white/90">Trading Sessions</h3>
              {!showCreateForm && (
                <Button variant="primary" onClick={() => setShowCreateForm(true)}>
                  + New Session
                </Button>
              )}
            </div>
            
            {showCreateForm && (
              <div className="mb-6 p-6 rounded-xl border-2 border-primary/20 bg-primary/5 dark:bg-primary/10">
                <h4 className="text-lg font-semibold text-gray-800 dark:text-white/90 mb-4">Create New Session</h4>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Strategy
                    </label>
                    <select
                      className="w-full rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-gray-900 py-3 px-4 text-gray-800 dark:text-white/90 outline-none transition focus:border-primary"
                      value={formData.strategy_name}
                      onChange={(e) => setFormData({ ...formData, strategy_name: e.target.value })}
                    >
                      <option value="">Select a strategy</option>
                      {strategies.map(strat => (
                        <option key={strat.key} value={strat.key}>
                          {strat.key}
                        </option>
                      ))}
                    </select>
                    {selectedStrategy?.doc && (
                      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{selectedStrategy.doc}</p>
                    )}
                  </div>
                  
                  {selectedStrategy && selectedStrategy.presets && Object.keys(selectedStrategy.presets).length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Load Preset (Optional)
                      </label>
                      <select
                        className="w-full rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-gray-900 py-3 px-4 text-gray-800 dark:text-white/90 outline-none transition focus:border-primary"
                        value={selectedPreset}
                        onChange={(e) => setSelectedPreset(e.target.value)}
                      >
                        <option value="">Custom (use defaults)</option>
                        {Object.keys(selectedStrategy.presets).map(presetName => (
                          <option key={presetName} value={presetName}>
                            {presetName}
                          </option>
                        ))}
                      </select>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Select a preset to load pre-configured parameters
                      </p>
                    </div>
                  )}
                  
                  {selectedStrategy?.params_schema?.properties ? (
                    <div className="space-y-3 p-4 rounded-lg bg-white dark:bg-gray-900">
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Parameters</p>
                      <div className="grid grid-cols-2 gap-3">
                        {Object.entries(selectedStrategy.params_schema.properties as Record<string, { type?: string; title?: string; default?: unknown }>).map(([key, schema]) => {
                          const rawValue = selectedParams[key];
                          const displayValue = typeof rawValue === "string" || typeof rawValue === "number" ? String(rawValue) : "";
                          const title = typeof schema.title === "string" ? schema.title : key;
                          return (
                          <div key={key}>
                            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                              {title}
                            </label>
                            <input
                              type={schema.type === "integer" || schema.type === "number" ? "number" : "text"}
                              className="w-full rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-gray-900 py-2 px-3 text-sm text-gray-800 dark:text-white/90 outline-none transition focus:border-primary"
                              value={displayValue}
                              onChange={(e) => {
                                const value = schema.type === "number" || schema.type === "integer" 
                                  ? parseFloat(e.target.value)
                                  : e.target.value;
                                setSelectedParams({ ...selectedParams, [key]: value });
                              }}
                              step={schema.type === "number" ? "any" : undefined}
                            />
                          </div>
                        );
                        })}
                      </div>
                    </div>
                  ) : null}
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Instrument
                      </label>
                      <select
                        className="w-full rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-gray-900 py-3 px-4 text-gray-800 dark:text-white/90 outline-none transition focus:border-primary"
                        value={formData.instrument}
                        onChange={(e) => setFormData({ ...formData, instrument: e.target.value })}
                      >
                        <option value="EUR_USD">EUR/USD</option>
                        <option value="GBP_USD">GBP/USD</option>
                        <option value="USD_JPY">USD/JPY</option>
                        <option value="AUD_USD">AUD/USD</option>
                        <option value="USD_CAD">USD/CAD</option>
                        <option value="XAU_USD">Gold</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Time Frame
                      </label>
                      <select
                        className="w-full rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-gray-900 py-3 px-4 text-gray-800 dark:text-white/90 outline-none transition focus:border-primary"
                        value={formData.granularity}
                        onChange={(e) => setFormData({ ...formData, granularity: e.target.value })}
                      >
                        <optgroup label="Seconds">
                          <option value="S5">5 Seconds</option>
                          <option value="S10">10 Seconds</option>
                          <option value="S15">15 Seconds</option>
                          <option value="S30">30 Seconds</option>
                        </optgroup>
                        <optgroup label="Minutes">
                          <option value="M1">1 Minute</option>
                          <option value="M2">2 Minutes</option>
                          <option value="M5">5 Minutes</option>
                          <option value="M15">15 Minutes</option>
                          <option value="M30">30 Minutes</option>
                        </optgroup>
                        <optgroup label="Hours">
                          <option value="H1">1 Hour</option>
                          <option value="H2">2 Hours</option>
                          <option value="H4">4 Hours</option>
                        </optgroup>
                        <optgroup label="Daily">
                          <option value="D">Daily</option>
                        </optgroup>
                      </select>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Max Position Size (units)
                      </label>
                      <input
                        type="number"
                        className="w-full rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-gray-900 py-3 px-4 text-gray-800 dark:text-white/90 outline-none transition focus:border-primary"
                        value={formData.max_position_size}
                        onChange={(e) => setFormData({ ...formData, max_position_size: parseInt(e.target.value) || 10000 })}
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        ≈ ${(formData.max_position_size / 10000).toFixed(2)} per pip on EUR/USD
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Max Daily Loss
                      </label>
                      <input
                        type="number"
                        className="w-full rounded-lg border border-stroke dark:border-strokedark bg-white dark:bg-gray-900 py-3 px-4 text-gray-800 dark:text-white/90 outline-none transition focus:border-primary"
                        value={formData.max_daily_loss}
                        onChange={(e) => setFormData({ ...formData, max_daily_loss: parseFloat(e.target.value) })}
                      />
                    </div>
                  </div>
                  
                  <div className="flex gap-3">
                    <Button variant="primary" onClick={handleCreateSession}>
                      Create Session
                    </Button>
                    <Button variant="outline" onClick={() => setShowCreateForm(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              </div>
            )}
            
            {accountSessions.length === 0 ? (
              <div className="text-center py-12 border-2 border-dashed border-stroke dark:border-strokedark rounded-xl">
                <p className="text-gray-500 dark:text-gray-400 mb-4">No trading sessions yet</p>
                {!showCreateForm && (
                  <Button variant="primary" onClick={() => setShowCreateForm(true)}>
                    Create First Session
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {accountSessions.map((session) => (
                  <SessionCard
                    key={session.session_id}
                    session={session}
                    positions={positions[session.session_id] || []}
                    trades={trades[session.session_id] || { open: [], closed: [] }}
                    onStartSession={onStartSession}
                    onStopSession={onStopSession}
                    onPauseSession={onPauseSession}
                    onResumeSession={onResumeSession}
                    onDeleteSession={onDeleteSession}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PaperTradingPage() {
  const [accounts, setAccounts] = useState<AccountInfo[]>([]);
  const [sessions, setSessions] = useState<PaperSession[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [selectedAccount, setSelectedAccount] = useState<AccountInfo | null>(null);
  const [positions, setPositions] = useState<Record<string, Position[]>>({});
  const [trades, setTrades] = useState<Record<string, { open: Trade[]; closed: Trade[] }>>({});
  
  const [lastUpdateTime, setLastUpdateTime] = useState<number>(Date.now());
  const [isConnected, setIsConnected] = useState(true);
  
  const wsRef = useRef<WebSocket | null>(null);
  
  const sortedAccounts = useMemo(() => {
    if (!accounts.length) return [] as AccountInfo[];
    const runningAccounts = new Set(
      sessions.filter((s) => s.status === "running").map((s) => s.account_id)
    );
    const capitalOf = (account: AccountInfo) => {
      const nav = Number(account.nav);
      if (Number.isFinite(nav) && nav > 0) return nav;
      const balance = Number(account.balance);
      return Number.isFinite(balance) ? balance : 0;
    };
    return [...accounts].sort((a, b) => {
      const aLive = runningAccounts.has(a.id);
      const bLive = runningAccounts.has(b.id);
      if (aLive !== bLive) return aLive ? -1 : 1;
      const capitalDiff = capitalOf(b) - capitalOf(a);
      if (capitalDiff !== 0) return capitalDiff;
      return (a.alias || a.id).localeCompare(b.alias || b.id);
    });
  }, [accounts, sessions]);
  
  useEffect(() => {
    loadData();
  }, []);
  
  useEffect(() => {
    const wsUrl = getWebSocketUrl();
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
      setLastUpdateTime(Date.now());
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "sessions_update") {
          setSessions(data.sessions);
          setLastUpdateTime(Date.now());
          setIsConnected(true);
        }
      } catch (e) {
        console.error("WebSocket error:", e);
      }
    };
    
    ws.onerror = () => {
      setIsConnected(false);
    };
    
    ws.onclose = () => {
      console.log("WebSocket closed");
      setIsConnected(false);
    };
    
    wsRef.current = ws;
    
    return () => {
      ws.close();
    };
  }, []);
  
  useEffect(() => {
    if (sessions.length > 0) {
      sessions.forEach(session => {
        fetchPositions(session.session_id);
        fetchTrades(session.session_id);
      });
      const interval = setInterval(() => {
        sessions.forEach(session => {
          fetchPositions(session.session_id);
          fetchTrades(session.session_id);
        });
        void loadAccounts();
        setLastUpdateTime(Date.now());
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [sessions]);
  
  // Check connection status
  useEffect(() => {
    const checkInterval = setInterval(() => {
      const timeSinceUpdate = Date.now() - lastUpdateTime;
      // If no update in 15 seconds, consider disconnected
      if (timeSinceUpdate > 15000) {
        setIsConnected(false);
      }
    }, 1000);
    return () => clearInterval(checkInterval);
  }, [lastUpdateTime]);
  
  async function loadData() {
    setLoading(true);
    try {
      const [accountsRes, sessionsRes, strategiesRes] = await Promise.all([
        fetch(`${BE}/paper-trading/accounts`),
        fetch(`${BE}/paper-trading/sessions`),
        fetch(`${BE}/backtest/strategies`),
      ]);
      setLastUpdateTime(Date.now());
      setIsConnected(true);
      
      if (!accountsRes.ok || !sessionsRes.ok || !strategiesRes.ok) {
        throw new Error("Failed to fetch data");
      }
      
      const accountsData = await accountsRes.json();
      const sessionsData = await sessionsRes.json();
      const strategiesData = await strategiesRes.json();
      
      setAccounts(accountsData);
      setSessions(sessionsData);
      setStrategies(strategiesData.strategies || []);
      setError(null);
    } catch (err: unknown) {
      console.error("Error loading data:", err);
      setError((err as Error).message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }
  
  async function loadAccounts() {
    try {
      const accountsRes = await fetch(`${BE}/paper-trading/accounts`);
      if (!accountsRes.ok) {
        return;
      }
      const accountsData = await accountsRes.json();
      setAccounts(accountsData);
    } catch {
      console.warn("loadAccounts skipped");
    }
  }
  
  async function fetchPositions(sessionId: string) {
    try {
      const res = await fetch(`${BE}/paper-trading/sessions/${sessionId}/positions`);
      if (res.status === 404) {
        setPositions(prev => {
          const next = { ...prev };
          delete next[sessionId];
          return next;
        });
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setPositions(prev => ({ ...prev, [sessionId]: data.positions || [] }));
      }
    } catch {
    }
  }
  
  async function fetchTrades(sessionId: string) {
    try {
      const res = await fetch(`${BE}/paper-trading/sessions/${sessionId}/trades`);
      if (res.status === 404) {
        setTrades(prev => {
          const next = { ...prev };
          delete next[sessionId];
          return next;
        });
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setTrades(prev => ({ 
          ...prev, 
          [sessionId]: { 
            open: data.open_trades || [], 
            closed: data.closed_trades || [] 
          } 
        }));
      }
    } catch {
    }
  }
  
  async function createSession(data: Record<string, unknown>) {
    try {
      const res = await fetch(`${BE}/paper-trading/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed to create session");
      }
      
      await loadData();
    } catch (err: unknown) {
      alert((err as Error).message || "Failed to create session");
    }
  }
  
  async function startSession(sessionId: string) {
    try {
      const res = await fetch(`${BE}/paper-trading/sessions/${sessionId}/start`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to start session");
      await loadData();
      setTimeout(() => {
        fetchTrades(sessionId);
        fetchPositions(sessionId);
      }, 2000);
    } catch (err: unknown) {
      alert((err as Error).message || "Failed to start session");
    }
  }
  
  async function stopSession(sessionId: string) {
    try {
      const res = await fetch(`${BE}/paper-trading/sessions/${sessionId}/stop`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to stop session");
      await loadData();
      setTimeout(() => {
        fetchTrades(sessionId);
        fetchPositions(sessionId);
      }, 2000);
    } catch (err: unknown) {
      alert((err as Error).message || "Failed to stop session");
    }
  }
  
  async function pauseSession(sessionId: string) {
    try {
      const res = await fetch(`${BE}/paper-trading/sessions/${sessionId}/pause`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to pause session");
      await loadData();
      setTimeout(() => {
        fetchTrades(sessionId);
        fetchPositions(sessionId);
      }, 2000);
    } catch (err: unknown) {
      alert((err as Error).message || "Failed to pause session");
    }
  }
  
  async function resumeSession(sessionId: string) {
    try {
      const res = await fetch(`${BE}/paper-trading/sessions/${sessionId}/resume`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to resume session");
      await loadData();
      setTimeout(() => {
        fetchTrades(sessionId);
        fetchPositions(sessionId);
      }, 2000);
    } catch (err: unknown) {
      alert((err as Error).message || "Failed to resume session");
    }
  }
  
  async function deleteSession(sessionId: string) {
    if (!confirm("Are you sure you want to delete this session?")) return;
    
    try {
      const res = await fetch(`${BE}/paper-trading/sessions/${sessionId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete session");
      await loadData();
    } catch (err: unknown) {
      alert((err as Error).message || "Failed to delete session");
    }
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
              <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-gray-500 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="rounded-xl border border-error bg-error/10 p-6">
        <h2 className="text-lg font-semibold text-error mb-2">Error</h2>
        <p className="text-gray-700 dark:text-gray-300">{error}</p>
        <Button className="mt-4" onClick={loadData}>
          Retry
        </Button>
      </div>
    );
  }
  
  const totalUnrealizedPL = accounts.reduce((sum, acc) => sum + acc.unrealized_pl, 0);
  const totalPositions = accounts.reduce((sum, acc) => sum + acc.open_position_count, 0);
  const activeSessions = sessions.filter(s => s.status === "running").length;
  
  return (
    <div className="space-y-6">
      <div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-white/90 mb-2">
            Paper Trading
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Live paper trading with OANDA demo accounts
          </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-gray-900">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Total Accounts</p>
          <p className="text-3xl font-bold text-gray-800 dark:text-white/90">{accounts.length}</p>
        </div>
        <div className="p-5 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-gray-900">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Active Sessions</p>
          <p className="text-3xl font-bold text-gray-800 dark:text-white">{activeSessions}</p>
        </div>
        <div className="p-5 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-gray-900">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Total Positions</p>
          <p className="text-3xl font-bold text-gray-800 dark:text-white/90">{totalPositions}</p>
        </div>
        <div className="p-5 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-gray-900">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Total P&L</p>
          <p className={`text-3xl font-bold ${totalUnrealizedPL >= 0 ? 'text-gray-800 dark:text-white' : 'text-gray-800 dark:text-white'}`}>
            {totalUnrealizedPL >= 0 ? '+' : ''}${totalUnrealizedPL.toFixed(2)}
          </p>
        </div>
      </div>
      
      {!isConnected && (
        <div className="mb-4 rounded-lg border-2 border-warning bg-warning/10 dark:bg-warning/20 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-3 w-3 rounded-full bg-warning animate-pulse"></div>
            <div>
              <p className="text-sm font-medium text-gray-800 dark:text-white">
                Connection Lost
              </p>
              <p className="text-xs text-gray-600 dark:text-gray-400">
                Frontend hasn&apos;t received updates. Your strategy may still be running - check backend logs or OANDA account.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              window.location.reload();
            }}
          >
            Refresh Page
          </Button>
        </div>
      )}
      
      <ConnectionStatus 
        isConnected={isConnected} 
        lastUpdateTime={lastUpdateTime} 
      />
      
      <div>
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white/90 mb-2">
          OANDA Accounts
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Select an account for more information and session management.
        </p>
        {sortedAccounts.length === 0 ? (
          <div className="rounded-xl border-2 border-dashed border-stroke dark:border-strokedark bg-white dark:bg-gray-900 p-12 text-center">
            <p className="text-gray-500 dark:text-gray-400 mb-2">No OANDA accounts found</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Please check your API credentials in the backend .env file</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sortedAccounts.map((account) => (
              <AccountCard
                key={account.id}
                account={account}
                sessions={sessions}
                onClick={() => setSelectedAccount(account)}
              />
            ))}
          </div>
        )}
      </div>
      
      <AccountManagementModal
        isOpen={selectedAccount !== null}
        onClose={() => setSelectedAccount(null)}
        account={selectedAccount}
        sessions={sessions}
        strategies={strategies}
        onCreateSession={createSession}
        onStartSession={startSession}
        onStopSession={stopSession}
        onPauseSession={pauseSession}
        onResumeSession={resumeSession}
        onDeleteSession={deleteSession}
        positions={positions}
        trades={trades}
      />
    </div>
  );
}
