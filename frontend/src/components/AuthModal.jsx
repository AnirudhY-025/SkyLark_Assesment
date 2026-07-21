import React, { useState } from 'react';
import { supabase } from '../lib/supabase';
import { Lock, Mail, LogIn, UserPlus, ShieldCheck, AlertCircle } from 'lucide-react';

export default function AuthModal({ onAuthSuccess, onGuestLogin }) {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        if (data?.user?.identities?.length === 0) {
          setErrorMsg('An account with this email already exists.');
        } else {
          setSuccessMsg('Account created successfully! Check your email for confirmation or log in.');
          if (data.session) onAuthSuccess(data.session);
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        if (data.session) onAuthSuccess(data.session);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-overlay">
      <div className="glass-card auth-card">
        <div className="auth-header">
          <div className="auth-icon-badge">
            <ShieldCheck size={28} color="#00f2fe" />
          </div>
          <h2>Skylark Executive Portal</h2>
          <p className="auth-subtitle">Enterprise BI Intelligence Suite</p>
        </div>

        <div className="auth-tabs">
          <button 
            className={`auth-tab ${!isSignUp ? 'active' : ''}`}
            onClick={() => { setIsSignUp(false); setErrorMsg(''); setSuccessMsg(''); }}
          >
            <LogIn size={15} />
            <span>Sign In</span>
          </button>
          <button 
            className={`auth-tab ${isSignUp ? 'active' : ''}`}
            onClick={() => { setIsSignUp(true); setErrorMsg(''); setSuccessMsg(''); }}
          >
            <UserPlus size={15} />
            <span>Register</span>
          </button>
        </div>

        {errorMsg && (
          <div className="auth-alert alert-error">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="auth-alert alert-success">
            <ShieldCheck size={16} />
            <span>{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleAuth} className="auth-form">
          <div className="input-group">
            <label>Work Email</label>
            <div className="input-wrapper">
              <Mail size={16} className="field-icon" />
              <input
                type="email"
                required
                placeholder="executive@skylarkdrones.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="input-group">
            <label>Password</label>
            <div className="input-wrapper">
              <Lock size={16} className="field-icon" />
              <input
                type="password"
                required
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <button type="submit" className="action-btn action-btn-primary auth-submit-btn" disabled={loading}>
            {loading ? (
              <span className="spinner"></span>
            ) : isSignUp ? (
              'Create Account'
            ) : (
              'Sign In to BI Portal'
            )}
          </button>
        </form>

        <div className="auth-divider">
          <span>OR</span>
        </div>

        <button className="guest-btn" onClick={onGuestLogin}>
          <span>Continue as Demo Guest Executive</span>
        </button>

        <div className="auth-footer">
          Secured with Supabase Auth & 256-bit TLS Encryption
        </div>
      </div>
    </div>
  );
}
