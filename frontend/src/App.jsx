import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Send, RefreshCw, FileText, ChevronDown, ChevronUp, 
  Database, Activity, TrendingUp, DollarSign, Briefcase, AlertCircle,
  LogOut, ShieldCheck
} from 'lucide-react';
import { supabase } from './lib/supabase';
import AuthModal from './components/AuthModal';

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [session, setSession] = useState(null);
  const [isGuest, setIsGuest] = useState(false);

  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Welcome! I'm your BI analyst for **Skylark Drones**. I can help you with:\n\n" +
               "- **Pipeline health** — deal values by stage, sector breakdown\n" +
               "- **Win rates** — conversion by sector, owner, or overall\n" +
               "- **Work order status** — billing, collections, outstanding AR\n" +
               "- **Sector performance** — revenue, pipeline, project counts\n" +
               "- **Leadership updates** — structured exec-ready briefs\n\n" +
               "What would you like to know today?"
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({ connected: false, work_orders_board_id: '', deals_board_id: '' });
  const [metrics, setMetrics] = useState(null);
  const [expandedTrace, setExpandedTrace] = useState({});
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) setSession(session);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session || isGuest) {
      fetchStatus();
      fetchMetrics();
    }
  }, [session, isGuest]);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      const data = await res.json();
      setStatus(data);
    } catch (e) {
      console.error('Failed to fetch status:', e);
    }
  };

  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/metrics`);
      const data = await res.json();
      if (!data.error) {
        setMetrics(data);
      }
    } catch (e) {
      console.error('Failed to fetch metrics:', e);
    }
  };

  const handleRefreshCache = async () => {
    try {
      await fetch(`${API_BASE}/api/refresh-cache`, { method: 'POST' });
      fetchMetrics();
    } catch (e) {
      console.error('Failed to refresh cache:', e);
    }
  };

  const sendMessage = async (userText) => {
    if (!userText.trim() || loading) return;

    const newMessages = [...messages, { role: 'user', content: userText }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: newMessages.map(m => ({ role: m.role, content: m.content || '' }))
        })
      });
      const data = await res.json();
      
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: data.response,
          tools_used: data.tools_used || []
        }
      ]);
    } catch (e) {
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: "⚠️ Sorry, I'm having trouble connecting to the backend server. Please make sure the API is running."
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleTrace = (index) => {
    setExpandedTrace(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    setSession(null);
    setIsGuest(false);
  };

  const quickPrompts = [
    { label: "📊 Pipeline by Sector", text: "Give me a breakdown of deal pipeline value by sector." },
    { label: "💰 Outstanding AR", text: "What is our total outstanding accounts receivable from work orders?" },
    { label: "📈 Win Rate Summary", text: "What is our overall win rate and win rate by sector?" },
    { label: "⚠️ Stuck Work Orders", text: "Which work orders are currently stuck or paused?" }
  ];

  const dealsMetric = metrics?.deals || {};
  const woMetric = metrics?.work_orders || {};

  const formatCurrency = (val) => {
    if (!val) return '₹0';
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)} Cr`;
    if (val >= 100000) return `₹${(val / 100000).toFixed(1)} L`;
    return `₹${val.toLocaleString()}`;
  };

  const isAuthenticated = session || isGuest;

  // ── Standalone Login View when unauthenticated ──
  if (!isAuthenticated) {
    return (
      <div className="standalone-auth-container">
        <AuthModal 
          onAuthSuccess={(s) => setSession(s)} 
          onGuestLogin={() => setIsGuest(true)} 
        />
      </div>
    );
  }

  // ── Main Authenticated Dashboard Layout ──
  return (
    <div className="app-layout">
      {/* ── Navbar Header ── */}
      <header className="navbar glass-card">
        <div className="brand-section">
          <div className="brand-icon">🛰️</div>
          <div>
            <div className="brand-title">Skylark Drones</div>
            <div className="brand-subtitle">Business Intelligence Suite</div>
          </div>
        </div>

        <div className="nav-actions">
          <div className="status-badge">
            <span className="status-dot"></span>
            <span>{status.connected ? "monday.com Connected" : "Connecting..."}</span>
          </div>

          <div className="user-profile-badge">
            <div className="user-avatar-small">
              {(session?.user?.email?.[0] || 'G').toUpperCase()}
            </div>
            <span className="user-email-text">
              {session?.user?.email || 'Demo Executive'}
            </span>
            <button className="logout-btn" title="Sign Out" onClick={handleSignOut}>
              <LogOut size={14} />
            </button>
          </div>

          <button className="action-btn" onClick={handleRefreshCache} title="Clear in-memory cache">
            <RefreshCw size={15} />
            <span>Refresh Cache</span>
          </button>

          <button className="action-btn action-btn-primary" onClick={() => sendMessage("Give me a leadership update on overall performance.")}>
            <FileText size={15} />
            <span>Leadership Brief</span>
          </button>
        </div>
      </header>

      {/* ── KPI Summary Bar ── */}
      <section className="metrics-grid">
        <div className="glass-card metric-card glass-card-interactive">
          <div className="metric-header">
            <span>Open Pipeline</span>
            <TrendingUp size={16} color="#00f2fe" />
          </div>
          <div className="metric-value">{formatCurrency(dealsMetric.pipeline_value)}</div>
          <div className="metric-sub">{dealsMetric.open_deals || 0} active deals in pipeline</div>
        </div>

        <div className="glass-card metric-card glass-card-interactive">
          <div className="metric-header">
            <span>Revenue Billed</span>
            <DollarSign size={16} color="#34d399" />
          </div>
          <div className="metric-value">{formatCurrency(woMetric.total_billed)}</div>
          <div className="metric-sub">Across {woMetric.total_orders || 0} total work orders</div>
        </div>

        <div className="glass-card metric-card glass-card-interactive">
          <div className="metric-header">
            <span>Overall Win Rate</span>
            <Activity size={16} color="#a855f7" />
          </div>
          <div className="metric-value">{dealsMetric.win_rate_pct ? `${dealsMetric.win_rate_pct}%` : '0%'}</div>
          <div className="metric-sub">{dealsMetric.won_count || 0} Won vs {dealsMetric.lost_count || 0} Lost</div>
        </div>

        <div className="glass-card metric-card glass-card-interactive">
          <div className="metric-header">
            <span>Outstanding AR</span>
            <AlertCircle size={16} color="#f59e0b" />
          </div>
          <div className="metric-value">{formatCurrency(woMetric.total_receivable)}</div>
          <div className="metric-sub">{woMetric.stuck_or_paused || 0} stuck/paused projects</div>
        </div>
      </section>

      {/* ── Main Chat Area ── */}
      <main className="dashboard-content glass-card">
        <div className="chat-container">
          <div className="chat-messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-row ${msg.role === 'user' ? 'message-user' : 'message-assistant'}`}>
                <div className={`avatar ${msg.role === 'user' ? 'avatar-user' : 'avatar-assistant'}`}>
                  {msg.role === 'user' ? 'YOU' : 'AI'}
                </div>
                <div className="message-content-wrapper">
                  <div className={`bubble ${msg.role === 'user' ? 'bubble-user' : 'bubble-assistant'}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>

                  {/* Render Data Source Trace dropdown if tools were executed */}
                  {msg.tools_used && msg.tools_used.length > 0 && (
                    <div className="tool-trace-card">
                      <div className="tool-trace-header" onClick={() => toggleTrace(idx)}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Database size={14} />
                          <span>📡 Data Source Trace (monday.com live query)</span>
                        </div>
                        {expandedTrace[idx] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </div>

                      {expandedTrace[idx] && (
                        <div className="tool-trace-body">
                          {msg.tools_used.map((tool, tIdx) => (
                            <div key={tIdx} style={{ marginBottom: 12 }}>
                              <div style={{ color: '#00f2fe', fontWeight: 600 }}>Tool Executed: {tool.name}</div>
                              {tool.arguments && Object.keys(tool.arguments).length > 0 && (
                                <div style={{ color: '#94a3b8', margin: '4px 0' }}>
                                  Filters: {JSON.stringify(tool.arguments)}
                                </div>
                              )}
                              <div style={{ color: '#64748b', marginTop: 4 }}>Raw Result Preview:</div>
                              <pre style={{ overflowX: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.75rem', marginTop: 2 }}>
                                {tool.result_snippet}
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="message-row message-assistant">
                <div className="avatar avatar-assistant">AI</div>
                <div className="bubble bubble-assistant" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="spinner"></div>
                  <span>Querying monday.com live GraphQL API...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompts Chips */}
          <div className="quick-prompts">
            {quickPrompts.map((qp, idx) => (
              <button key={idx} className="chip" onClick={() => sendMessage(qp.text)}>
                {qp.label}
              </button>
            ))}
          </div>

          {/* Chat Input */}
          <div className="chat-input-area">
            <form 
              className="input-form" 
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage(input);
              }}
            >
              <input
                type="text"
                className="input-field"
                placeholder="Ask about pipeline health, win rates, work orders, revenue, sector performance..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
              />
              <button type="submit" className="send-btn" disabled={!input.trim() || loading}>
                <Send size={18} />
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
