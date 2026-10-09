import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search, Plus, RefreshCw, Key, ChevronDown, ChevronUp, ChevronRight,
  AlertTriangle, CheckCircle, ShieldCheck, Shield, Cloud, Briefcase,
  Mail, Video, BarChart2, Zap, Code, ShieldAlert, TrendingUp,
  Headphones, Globe, Layers, Database, Bot, Sparkles, Filter,
  Users, UserCheck, X, ExternalLink, Copy, Check, MoreVertical,
  Send, ClipboardList, Clock,
} from 'lucide-react';
import { Badge, Spinner, EmptyState, ProgressBar, Modal, AlertBanner, ToolLogo } from '../components/ui';
import { mockLicenses } from '../api/mockData';
import {
  getLicenses, triggerSync, getLicenseUsers, getAppAssignedUsers,
  createLicenseRequest, getLicenseRequests, finalizeLicenseRequest,
} from '../api/services';
import { useAuth } from '../context/AuthContext';
import {
  formatDate, formatNumber, formatPercent, capitalize, daysUntil, getExpiryUrgency, getUtilizationLevel,
} from '../utils/formatters';

const CATEGORY_ICONS = {
  'Business Suite': ShieldCheck,
  'Productivity & Cloud': Cloud,
  'Enterprise Cloud': Briefcase,
  'Messaging & Email': Mail,
  'Collaboration & Meetings': Video,
  'Analytics & BI': BarChart2,
  'Automation & Workflows': Zap,
  'Developer & Sandbox': Code,
  'Cybersecurity & Identity': ShieldAlert,
  'CRM & Sales': TrendingUp,
  'Customer Service & Support': Headphones,
  'Low-Code Web Apps': Globe,
  'Enterprise ERP': Layers,
  'Cloud ERP': Database,
  'AI & Copilot Studio': Bot,
  'Team Collaboration': Sparkles,
  'Visual Collaboration': Globe,
  'Cloud Storage': Cloud,
  'Video Conferencing': Video,
  'Project Management': Layers,
  'SASE & Security': ShieldAlert,
};

// ── License Users Modal ──────────────────────────────────────────────────────
const LicenseUsersModal = ({ open, license, onClose }) => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [userSearch, setUserSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [copiedEmail, setCopiedEmail] = useState('');

  useEffect(() => {
    if (!license || !open) return;
    let active = true;
    setLoading(true);
    getLicenseUsers(license)
      .then((res) => {
        if (active) setUsers(res.data || []);
      })
      .catch((err) => {
        console.warn('Failed to load license users:', err);
        if (active) setUsers([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [license, open]);

  if (!license) return null;

  const filteredUsers = users.filter((u) => {
    const q = userSearch.toLowerCase();
    const matchesSearch =
      !q ||
      u.name?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      u.department?.toLowerCase().includes(q) ||
      u.role?.toLowerCase().includes(q);
    const matchesStatus = statusFilter === 'all' || u.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleCopyEmail = (email) => {
    navigator.clipboard?.writeText(email);
    setCopiedEmail(email);
    setTimeout(() => setCopiedEmail(''), 2000);
  };

  const utilPct = license.total_quantity
    ? Math.min(100, Math.round(((license.allocated_quantity || license.used_quantity || 0) / license.total_quantity) * 100))
    : 0;

  return (
    <Modal
      open={open}
      title=""
      onClose={onClose}
      footer={<button className="btn btn-secondary" onClick={onClose}>Close</button>}
    >
      {/* Header Info */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ToolLogo name={license.application_name} size={42} />
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
              {license.license_name}
            </h3>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {license.application_name} · <span style={{ fontFamily: 'monospace' }}>{license.raw_sku_part_number || license.product_code || 'SKU'}</span>
            </div>
          </div>
        </div>
        <Badge variant={license.status === 'active' ? 'success' : 'neutral'}>
          {capitalize(license.status)}
        </Badge>
      </div>

      {/* Utilization & Seat Summary */}
      <div
        style={{
          background: 'var(--gray-50)',
          borderRadius: 10,
          padding: '12px 16px',
          border: '1px solid var(--border-color)',
          marginBottom: 16,
        }}
      >
        <div className="flex-between" style={{ marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
            Assigned Seats: {formatNumber(license.allocated_quantity || license.used_quantity || 0)} / {formatNumber(license.total_quantity || 0)}
          </span>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
            {utilPct}% Used
          </span>
        </div>
        <ProgressBar value={utilPct} max={100} />
        <div className="flex-between" style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
          <span>{formatNumber(license.available_quantity || 0)} available seats in pool</span>
          <span>Renewal: {formatDate(license.expiry_date)}</span>
        </div>
      </div>

      {/* Search & Status Filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <div className="input-with-icon" style={{ flex: 1, minWidth: 200 }}>
          <span className="input-icon"><Search size={14} /></span>
          <input
            className="input"
            placeholder="Search assigned users by name, email, department…"
            value={userSearch}
            onChange={(e) => setUserSearch(e.target.value)}
            style={{ height: 34, fontSize: 13 }}
          />
        </div>
        <select
          className="select"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ height: 34, fontSize: 13 }}
        >
          <option value="all">All Statuses ({users.length})</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Users Table */}
      {loading ? (
        <div style={{ padding: '30px 0', textAlign: 'center' }}>
          <Spinner size={30} />
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
            Fetching users assigned to this license…
          </div>
        </div>
      ) : filteredUsers.length === 0 ? (
        <EmptyState
          icon={<Users size={22} color="var(--gray-400)" />}
          title="No users found"
          description={userSearch ? 'No assigned users match your search query.' : 'No users currently assigned to this license.'}
        />
      ) : (
        <div style={{ maxHeight: 340, overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: 8 }}>
          <table className="table" style={{ margin: 0 }}>
            <thead>
              <tr style={{ background: 'var(--gray-50)', position: 'sticky', top: 0, zIndex: 1 }}>
                <th style={{ padding: '8px 12px', fontSize: 11 }}>User</th>
                <th style={{ padding: '8px 12px', fontSize: 11 }}>Department / Role</th>
                <th style={{ padding: '8px 12px', fontSize: 11 }}>Status</th>
                <th style={{ padding: '8px 12px', fontSize: 11 }}>Assigned Date</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u, idx) => (
                <tr key={u.user_id || u.email || idx}>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div
                        style={{
                          width: 30,
                          height: 30,
                          borderRadius: '50%',
                          background: 'linear-gradient(135deg, var(--primary-500), var(--primary-700))',
                          color: 'white',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: 600,
                          fontSize: 12,
                          flexShrink: 0,
                        }}
                      >
                        {u.name?.charAt(0)?.toUpperCase() || 'U'}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>
                          {u.name}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{u.email}</span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCopyEmail(u.email);
                            }}
                            title="Copy email"
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              padding: 2,
                              color: copiedEmail === u.email ? 'var(--success-600)' : 'var(--gray-400)',
                            }}
                          >
                            {copiedEmail === u.email ? <Check size={11} /> : <Copy size={11} />}
                          </button>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ fontSize: 12, fontWeight: 500 }}>{u.role || 'Member'}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{u.department || 'General'}</div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <Badge variant={u.status === 'active' ? 'success' : 'neutral'}>
                      {capitalize(u.status || 'active')}
                    </Badge>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-muted)' }}>
                    {u.assigned_date ? formatDate(u.assigned_date) : 'Active'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
};

// ── App-Level Users Modal (Admin / Users tiles) ──────────────────────────────
// ★ SINGLE PLACE TO CHANGE THE ADMIN ROLE ★
// A user counts as an "admin" only if their role matches one of these values
// (case-insensitive, exact match). Used by the Admin tile count and the
// Admins modal. E.g. to switch later: ['Global Administrator', 'Privileged Administrator']
const ADMIN_ROLES = ['Global Administrator'];
const isAdminRole = (role) => {
  if (!role) return false;
  const r = role.toLowerCase().trim();
  return ADMIN_ROLES.some((a) => r === a.toLowerCase().trim());
};

const AppUsersModal = ({ open, appName, roleFilter, users, onClose }) => {
  const [userSearch, setUserSearch] = useState('');
  const [copiedEmail, setCopiedEmail] = useState('');

  if (!open || !appName) return null;

  const title = roleFilter === 'admin' ? `${appName} — Admins` : `${appName} — All Users`;

  const displayUsers = roleFilter === 'admin'
    ? users.filter((u) => isAdminRole(u.role))
    : users;

  const filteredUsers = displayUsers.filter((u) => {
    const q = userSearch.toLowerCase();
    return (
      !q ||
      u.name?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      u.department?.toLowerCase().includes(q) ||
      u.role?.toLowerCase().includes(q)
    );
  });

  const handleCopyEmail = (email) => {
    navigator.clipboard?.writeText(email);
    setCopiedEmail(email);
    setTimeout(() => setCopiedEmail(''), 2000);
  };

  return (
    <Modal
      open={open}
      title=""
      onClose={onClose}
      footer={<button className="btn btn-secondary" onClick={onClose}>Close</button>}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <ToolLogo name={appName} size={42} />
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
            {title}
          </h3>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            {displayUsers.length} {roleFilter === 'admin' ? 'administrators' : 'users'} · sourced from license_assigned_users
          </div>
        </div>
      </div>

      {/* Summary Badges */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        <Badge variant={roleFilter === 'admin' ? 'info' : 'success'}>
          {roleFilter === 'admin' ? <Shield size={12} /> : <Users size={12} />}
          <span style={{ marginLeft: 4 }}>{displayUsers.length} {roleFilter === 'admin' ? 'Admins' : 'Total Users'}</span>
        </Badge>
        <Badge variant="neutral">
          {displayUsers.filter((u) => u.status === 'active').length} Active
        </Badge>
      </div>

      {/* Search */}
      <div style={{ marginBottom: 12 }}>
        <div className="input-with-icon" style={{ width: '100%' }}>
          <span className="input-icon"><Search size={14} /></span>
          <input
            className="input"
            placeholder="Search by name, email, role…"
            value={userSearch}
            onChange={(e) => setUserSearch(e.target.value)}
            style={{ height: 34, fontSize: 13 }}
          />
        </div>
      </div>

      {/* Table */}
      {filteredUsers.length === 0 ? (
        <EmptyState
          icon={<Users size={22} color="var(--gray-400)" />}
          title="No users found"
          description={userSearch ? 'No users match your search.' : `No ${roleFilter === 'admin' ? 'administrators' : 'users'} for this application.`}
        />
      ) : (
        <div style={{ maxHeight: 380, overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: 8 }}>
          <table className="table" style={{ margin: 0 }}>
            <thead>
              <tr style={{ background: 'var(--gray-50)', position: 'sticky', top: 0, zIndex: 1 }}>
                <th style={{ padding: '8px 12px', fontSize: 11 }}>User</th>
                <th style={{ padding: '8px 12px', fontSize: 11 }}>Role</th>
                <th style={{ padding: '8px 12px', fontSize: 11 }}>License</th>
                <th style={{ padding: '8px 12px', fontSize: 11 }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u, idx) => (
                <tr key={u.user_id || u.email || idx}>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div
                        style={{
                          width: 30, height: 30, borderRadius: '50%',
                          background: roleFilter === 'admin'
                            ? 'linear-gradient(135deg, #2563eb, #1e40af)'
                            : 'linear-gradient(135deg, var(--primary-500), var(--primary-700))',
                          color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontWeight: 600, fontSize: 12, flexShrink: 0,
                        }}
                      >
                        {u.name?.charAt(0)?.toUpperCase() || 'U'}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{u.name}</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{u.email}</span>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleCopyEmail(u.email); }}
                            title="Copy email"
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: copiedEmail === u.email ? 'var(--success-600)' : 'var(--gray-400)' }}
                          >
                            {copiedEmail === u.email ? <Check size={11} /> : <Copy size={11} />}
                          </button>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ fontSize: 12, fontWeight: 500 }}>{u.role || 'Member'}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{u.department || 'General'}</div>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-secondary)' }}>
                    {u.license_name || '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <Badge variant={u.status === 'active' ? 'success' : 'neutral'}>
                      {capitalize(u.status || 'active')}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
};

// ── App Hero Header Banner Component (Matches Template Card) ───────────────
const APP_DESCRIPTIONS = {
  'Microsoft 365': 'Productivity tools, collaboration, and cloud services for your organization.',
  'Slack': 'Real-time team messaging, channels, and workplace integration platform.',
  'Lucidchart': 'Diagramming, flowcharts, and visual workspace for architecture & design.',
  'Box': 'Secure cloud content management, file sharing, and storage solution.',
  'Zoom': 'Video conferencing, webinars, and virtual meeting platform.',
  'Sofia - (Pilot)': 'AI-powered enterprise virtual assistant and automation platform.',
  '_Jira': 'Agile project tracking, issue management, and software workflow platform.',
  'CATO': 'Cloud-native SASE network security and zero-trust framework.',
};

const AppHeroCard = ({
  appName,
  appLicenses,
  appUserCounts,
  onOpenAdminModal,
  onOpenUsersModal,
  onManageLicenses,
}) => {
  const totalPurchased = appLicenses.reduce((acc, l) => acc + (l.total_quantity || 0), 0);
  const totalAssigned = appLicenses.reduce((acc, l) => acc + (l.allocated_quantity || l.used_quantity || 0), 0);
  const totalAvailable = Math.max(0, totalPurchased - totalAssigned);
  const utilPct = totalPurchased > 0 ? Math.min(100, Math.round((totalAssigned / totalPurchased) * 100)) : 0;
  const isActive = appLicenses.length > 0 ? appLicenses.some((l) => l.status === 'active') : true;
  const description = APP_DESCRIPTIONS[appName] || 'Enterprise software application license management and seat allocation.';

  // Fallback: 0 admins until real counts load (admins = ADMIN_ROLES match only)
  const adminCount = appUserCounts[appName]?.admins ?? 0;
  const totalUserCount = appUserCounts[appName]?.total ?? (totalAssigned || (appName === 'Microsoft 365' ? 999 : appName === 'Slack' ? 42 : 0));

  // Circular Donut SVG Parameters
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (circumference * utilPct) / 100;

  // Usage Health Rating
  const getHealthInfo = (pct) => {
    if (pct >= 95) return { label: 'High Usage', color: '#ea580c', text: 'Seat capacity near full utilization.' };
    if (pct >= 50) return { label: 'Good', color: '#16a34a', text: 'Your license usage is healthy.' };
    if (pct > 0) return { label: 'Optimal', color: '#2563eb', text: 'License capacity readily available.' };
    return { label: 'Pending', color: '#64748b', text: 'Software integration idle.' };
  };
  const health = getHealthInfo(utilPct);

  return (
    <div
      className="app-hero-header-grid"
      style={{
        padding: '20px 24px',
        background: 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
        borderBottom: '1px solid var(--border-color)',
        display: 'grid',
        gridTemplateColumns: '1.25fr 1fr 0.85fr 0.9fr',
        gap: 20,
        alignItems: 'center',
      }}
    >
      {/* Panel 1: App Identity & Description */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ToolLogo name={appName} size={42} />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                {appName}
              </h2>
              <Badge variant={isActive ? 'success' : 'neutral'}>
                {isActive ? 'Active' : 'Inactive'}
              </Badge>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {appLicenses.length} {appLicenses.length === 1 ? 'license tier' : 'license tiers'}
            </div>
          </div>
        </div>

        <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 6px 0', lineHeight: 1.45 }}>
          {description}
        </p>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => onOpenUsersModal(appName)}
            style={{ borderRadius: 8, padding: '6px 14px', fontSize: 12, fontWeight: 600 }}
          >
            View Details
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={onManageLicenses}
            style={{ borderRadius: 8, padding: '6px 14px', fontSize: 12, fontWeight: 500, background: 'white', border: '1px solid var(--border-color)' }}
          >
            Manage Licenses
          </button>
        </div>
      </div>

      {/* Panel 2: Utilization Circular Donut & Seat Breakdown */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '14px 16px',
          background: 'white',
          borderRadius: 12,
          border: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ position: 'relative', width: 84, height: 84, flexShrink: 0 }}>
          <svg width="84" height="84" viewBox="0 0 90 90">
            <circle cx="45" cy="45" r={radius} fill="transparent" stroke="#e2e8f0" strokeWidth="9" />
            <circle
              cx="45"
              cy="45"
              r={radius}
              fill="transparent"
              stroke="#2563eb"
              strokeWidth="9"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              transform="rotate(-90 45 45)"
              style={{ transition: 'stroke-dashoffset 0.5s ease' }}
            />
            <text x="45" y="42" textAnchor="middle" fontSize="16" fontWeight="800" fill="var(--gray-900)">
              {utilPct}%
            </text>
            <text x="45" y="55" textAnchor="middle" fontSize="9" fontWeight="500" fill="var(--gray-500)">
              Utilization
            </text>
          </svg>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#2563eb' }} />
            <span style={{ fontWeight: 700, color: 'var(--gray-900)' }}>{formatNumber(totalAssigned)}</span>
            <span style={{ color: 'var(--gray-500)', fontSize: 11 }}>Assigned</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#cbd5e1' }} />
            <span style={{ fontWeight: 700, color: 'var(--gray-900)' }}>{formatNumber(totalAvailable)}</span>
            <span style={{ color: 'var(--gray-500)', fontSize: 11 }}>Available</span>
          </div>
          <div style={{ marginTop: 2, paddingTop: 4, borderTop: '1px solid #f1f5f9', fontSize: 12 }}>
            <span style={{ fontWeight: 800, color: 'var(--gray-900)' }}>{formatNumber(totalPurchased)}</span>{' '}
            <span style={{ fontWeight: 500, color: 'var(--gray-500)', fontSize: 11 }}>Total Seats</span>
          </div>
        </div>
      </div>

      {/* Panel 3: Admin & Users Stacked Tiles */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Admin Tile */}
        <button
          className="admin-tile-btn"
          onClick={() => onOpenAdminModal(appName)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '10px 14px',
            background: '#eff6ff',
            border: '1px solid #bfdbfe',
            borderRadius: 12,
            cursor: 'pointer',
            width: '100%',
            textAlign: 'left',
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              background: 'linear-gradient(135deg, #2563eb, #1e40af)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Shield size={17} color="white" />
          </div>
          <div style={{ flex: 1, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#1e3a8a' }}>Admin</div>
            <div style={{ fontSize: 11, color: '#3b82f6', fontWeight: 500 }}>
              {adminCount} {adminCount === 1 ? 'Admin' : 'Admins'}
            </div>
          </div>
          <ChevronRight size={15} color="#3b82f6" />
        </button>

        {/* Users Tile */}
        <button
          className="users-tile-btn"
          onClick={() => onOpenUsersModal(appName)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '10px 14px',
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: 12,
            cursor: 'pointer',
            width: '100%',
            textAlign: 'left',
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              background: 'linear-gradient(135deg, #16a34a, #15803d)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Users size={17} color="white" />
          </div>
          <div style={{ flex: 1, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#14532d' }}>Users</div>
            <div style={{ fontSize: 11, color: '#16a34a', fontWeight: 500 }}>
              {totalUserCount} {totalUserCount === 1 ? 'User' : 'Users'}
            </div>
          </div>
          <ChevronRight size={15} color="#16a34a" />
        </button>
      </div>

      {/* Panel 4: License Health Indicator */}
      <div
        style={{
          padding: '14px 16px',
          background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
          border: '1px solid #e2e8f0',
          borderRadius: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            License Health
          </span>
          <span style={{ fontSize: 12, color: 'var(--gray-400)', cursor: 'pointer' }} title="Overall usage health rating">ⓘ</span>
        </div>

        <div style={{ fontSize: 20, fontWeight: 800, color: health.color }}>
          {health.label}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 2 }}>
          <div style={{ flex: 1, height: 8, background: '#e2e8f0', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${utilPct}%`, background: health.color, borderRadius: 4, transition: 'width 0.4s ease' }} />
          </div>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--gray-800)' }}>{utilPct}%</span>
        </div>

        <div style={{ fontSize: 11, color: 'var(--gray-500)', marginTop: 2 }}>
          {health.text}
        </div>
      </div>
    </div>
  );
};

// ── License Request helpers (approval flow UI) ────────────────────────────────

const REQUEST_BADGE_VARIANT = {
  pending_tower_head: 'warning',
  pending_app_owner: 'warning',
  pending_it_review: 'info',
  approved: 'success',
  rejected: 'critical',
  cancelled: 'neutral',
};

const RequestStatusBadge = ({ status, label }) => (
  <Badge variant={REQUEST_BADGE_VARIANT[status] || 'neutral'}>
    {label || status}
  </Badge>
);

const STEP_STATE_META = {
  approved: { icon: CheckCircle, color: '#16a34a', text: 'Approved' },
  rejected: { icon: X, color: '#dc2626', text: 'Rejected' },
  pending: { icon: Clock, color: '#d97706', text: 'Pending — action needed' },
  waiting: { icon: Clock, color: '#94a3b8', text: 'Waiting for previous step' },
  skipped: { icon: X, color: '#94a3b8', text: 'Skipped' },
  cancelled: { icon: X, color: '#64748b', text: 'Cancelled' },
};

/**
 * Shows the 4-step pipeline (IT Team → Tower Head → App Owner → IT Team)
 * with WHOSE approval is currently pending, plus final-action buttons
 * when both email approvals are done (status === pending_it_review).
 */
const RequestPipeline = ({ req, onBack, onFinalAction }) => {
  const steps = req.steps || [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <button
        className="btn btn-secondary btn-sm"
        onClick={onBack}
        style={{ alignSelf: 'flex-start' }}
      >
        ← Back to requests
      </button>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 800, fontSize: 15 }}>{req.request_id}</span>
        <RequestStatusBadge status={req.status} label={req.status_label} />
      </div>

      {/* Summary */}
      <div style={{ fontSize: 13, color: '#475569', lineHeight: 1.7 }}>
        <div><b>License:</b> {req.license_name} ({req.license_type || '—'})</div>
        <div><b>Application:</b> {req.application_name} · {req.request_type} · Qty {req.quantity}</div>
        <div><b>Requested For:</b> {req.requested_for} ({req.requested_for_email})</div>
        <div><b>Raised By:</b> {req.submitted_by || 'IT Team'} ({req.submitted_by_email || '—'})</div>
        {req.justification && <div><b>Justification:</b> {req.justification}</div>}
      </div>

      {/* Pending callout */}
      {req.status.startsWith('pending_') && (
        <div
          style={{
            padding: '10px 14px', borderRadius: 8, fontSize: 13,
            background: '#fef3c7', border: '1px solid #fcd34d', color: '#92400e',
            fontWeight: 600,
          }}
        >
          <Clock size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          {req.status === 'pending_tower_head' && (
            <>Waiting on <b>Tower Head</b> ({req.tower_head?.name} — approval sent to {req.tower_head?.email})</>
          )}
          {req.status === 'pending_app_owner' && (
            <>Waiting on <b>Application Owner</b> ({req.app_owner?.name} — approval sent to {req.app_owner?.email})</>
          )}
          {req.status === 'pending_it_review' && (
            <>Both email approvals received — <b>IT Team</b> final action required below</>
          )}
        </div>
      )}

      {/* Pipeline steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {steps.map((s) => {
          const meta = STEP_STATE_META[s.state] || STEP_STATE_META.waiting;
          const Icon = meta.icon;
          return (
            <div
              key={s.order}
              style={{
                display: 'flex', gap: 12, padding: '10px 0',
                borderTop: s.order === 1 ? 'none' : '1px solid #eef2f7',
              }}
            >
              <div
                style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: `${meta.color}1a`, color: meta.color,
                }}
              >
                <Icon size={15} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 700, fontSize: 13 }}>{s.role}</span>
                  <Badge variant={s.channel === 'email' ? 'info' : 'neutral'}>
                    {s.channel === 'email' ? 'via email' : 'via portal'}
                  </Badge>
                  <span style={{ fontSize: 12, color: meta.color, fontWeight: 600 }}>
                    {meta.text}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                  {s.actor}
                  {s.at && ` · ${new Date(s.at).toLocaleString()}`}
                </div>
                {s.comment && (
                  <div style={{ fontSize: 12, color: '#475569', marginTop: 4, fontStyle: 'italic' }}>
                    “{s.comment}”
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* IT Team final action */}
      {req.status === 'pending_it_review' && (
        <div
          style={{
            display: 'flex', gap: 8, justifyContent: 'flex-end',
            borderTop: '1px solid #eef2f7', paddingTop: 12,
          }}
        >
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => onFinalAction(req.request_id, 'reject')}
          >
            <X size={14} /> Reject
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => onFinalAction(req.request_id, 'approve')}
          >
            <CheckCircle size={14} /> Approve & Complete
          </button>
        </div>
      )}
    </div>
  );
};

// ── Main Licenses Page ────────────────────────────────────────────────────────
const LicensesPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeAppParam = searchParams.get('app') || 'all';

  const [licenses, setLicenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterApp, setFilterApp] = useState(activeAppParam);
  const [filterType, setFilterType] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [viewMode, setViewMode] = useState('grouped'); // 'grouped' or 'flat'
  const [selectedLicense, setSelectedLicense] = useState(null);
  const [syncing, setSyncing] = useState(false);

  // ── License Request flow (IT Team → Tower Head → App Owner → IT Team) ──────
  const { user } = useAuth();
  const [showSubmitModal, setShowSubmitModal] = useState(false); // Submit Request popup
  const [showRequestsModal, setShowRequestsModal] = useState(false); // Requests list + pipeline
  const [requests, setRequests] = useState([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState(null); // pipeline detail
  const [submitting, setSubmitting] = useState(false);
  const [newReq, setNewReq] = useState({
    license_name: '',
    application_name: 'Microsoft 365',
    license_type: 'Business Suite',
    quantity: 1,
    request_type: 'New License',
    priority: 'Normal',
    justification: '',
    requested_for: '',
    requested_for_email: '',
    tower_head_name: '',
    tower_head_email: '',
    app_owner_name: '',
    app_owner_email: '',
  });

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [appUsersModal, setAppUsersModal] = useState(null); // { appName, roleFilter, users }
  const [appUserCounts, setAppUserCounts] = useState({}); // { 'Microsoft 365': { admins: N, total: N, users: [] }, ... }

  // Sync param to filter state
  useEffect(() => {
    if (activeAppParam) {
      setFilterApp(activeAppParam);
    }
  }, [activeAppParam]);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getLicenses();
      setLicenses(res.data);
    } catch (err) {
      console.warn('API error, falling back to mock data', err);
      setLicenses(mockLicenses);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // Fetch admin/user counts for active applications
  useEffect(() => {
    const fetchAppUsers = async () => {
      const activeApps = ['Microsoft 365', 'Slack'];
      const counts = {};
      for (const app of activeApps) {
        try {
          const users = await getAppAssignedUsers(app);
          const admins = users.filter((u) => isAdminRole(u.role));
          counts[app] = { admins: admins.length, total: users.length, users };
        } catch {
          counts[app] = { admins: 0, total: 0, users: [] };
        }
      }
      setAppUserCounts(counts);
    };
    fetchAppUsers();
  }, [licenses]);

  const handleSyncAll = async () => {
    setSyncing(true);
    try {
      await triggerSync('ms-graph');
      await load();
      setSuccess('Live Microsoft 365 & Slack licenses synchronized successfully!');
    } catch (err) {
      console.warn('Sync failed:', err);
    } finally {
      setSyncing(false);
      setTimeout(() => setSuccess(''), 3500);
    }
  };

  const loadRequests = async () => {
    setRequestsLoading(true);
    try {
      const list = await getLicenseRequests();
      setRequests(list);
    } catch {
      setRequests([]);
    } finally {
      setRequestsLoading(false);
    }
  };

  useEffect(() => {
    if (showRequestsModal) loadRequests();
  }, [showRequestsModal]);

  const openSubmitModal = () => {
    setNewReq((r) => ({
      ...r,
      submitted_by: user?.name || 'IT Team',
      submitted_by_email: user?.email || '',
    }));
    setShowSubmitModal(true);
  };

  const handleSubmitRequest = async () => {
    const required = [
      'license_name', 'requested_for', 'requested_for_email',
      'tower_head_name', 'tower_head_email',
      'app_owner_name', 'app_owner_email',
    ];
    const missing = required.find((k) => !String(newReq[k] || '').trim());
    if (missing) {
      setError('Please fill all required fields (marked with *).');
      setTimeout(() => setError(''), 4000);
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        ...newReq,
        quantity: Number(newReq.quantity) || 1,
        submitted_by: user?.name || 'IT Team',
        submitted_by_email: user?.email || '',
      };
      const res = await createLicenseRequest(payload);
      setShowSubmitModal(false);
      setSuccess(
        `Request ${res.data.request_id} submitted — approval email sent to `
        + `${res.data.tower_head.name}. Track it under "Requests".`
      );
      setNewReq((r) => ({
        license_name: '', license_type: r.license_type,
        application_name: r.application_name,
        quantity: 1, request_type: 'New License', priority: 'Normal',
        justification: '', requested_for: '', requested_for_email: '',
        tower_head_name: '', tower_head_email: '',
        app_owner_name: '', app_owner_email: '',
      }));
      loadRequests();
    } catch (err) {
      setError(
        err?.response?.data?.detail
          || 'Could not submit the request. Is the backend running?'
      );
      setTimeout(() => setError(''), 5000);
    } finally {
      setSubmitting(false);
      setTimeout(() => setSuccess(''), 6000);
    }
  };

  const handleFinalAction = async (requestId, action) => {
    try {
      await finalizeLicenseRequest(requestId, action);
      setSuccess(
        action === 'approve'
          ? `Request ${requestId} marked as Approved.`
          : `Request ${requestId} marked as Rejected.`
      );
      setSelectedRequest(null);
      loadRequests();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Final action failed.');
      setTimeout(() => setError(''), 5000);
    } finally {
      setTimeout(() => setSuccess(''), 5000);
    }
  };

  // All monitored tools
  const ALL_TOOLS = ['Microsoft 365', 'Slack', 'Lucidchart', 'Box', 'Zoom', 'Sofia - (Pilot)', '_Jira', 'CATO'];
  const appNames = ALL_TOOLS;
  const licenseTypes = [...new Set(licenses.map((l) => l.license_type).filter(Boolean))];

  // Filtering
  const filtered = licenses.filter((l) => {
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      l.license_name.toLowerCase().includes(q) ||
      l.raw_sku_part_number?.toLowerCase().includes(q) ||
      l.product_code?.toLowerCase().includes(q) ||
      l.application_name?.toLowerCase().includes(q) ||
      l.license_type?.toLowerCase().includes(q) ||
      l.vendor?.toLowerCase().includes(q);

    const matchApp =
      filterApp === 'all' ||
      l.application_name?.toLowerCase() === filterApp.toLowerCase();
    const matchType = filterType === 'all' || l.license_type === filterType;
    const matchStatus = filterStatus === 'all' || l.status === filterStatus;
    return matchSearch && matchApp && matchType && matchStatus;
  });

  // Group filtered licenses by application
  const groupedByApp = {};
  const toolsToDisplay =
    filterApp === 'all'
      ? ALL_TOOLS
      : ALL_TOOLS.filter((t) => t.toLowerCase() === filterApp.toLowerCase());

  toolsToDisplay.forEach((appName) => {
    groupedByApp[appName] = [];
  });

  filtered.forEach((lic) => {
    const app = lic.application_name || 'Other';
    if (!groupedByApp[app]) groupedByApp[app] = [];
    groupedByApp[app].push(lic);
  });

  const handleAppTabClick = (appName) => {
    setFilterApp(appName);
    if (appName === 'all') {
      searchParams.delete('app');
    } else {
      searchParams.set('app', appName);
    }
    setSearchParams(searchParams);
  };

  if (loading) return <Spinner />;

  return (
    <>
      {success && <AlertBanner type="success" message={success} onDismiss={() => setSuccess('')} />}
      {error && <AlertBanner type="error" message={error} onDismiss={() => setError('')} />}

      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Enterprise Licenses</h1>
          <p className="page-desc">
            {licenses.length} licenses organized across {appNames.length} applications · Click any license to inspect assigned users
          </p>
        </div>
        <div className="flex gap-8">
          <button
            id="licenses-sync-btn"
            className="btn btn-secondary btn-sm"
            onClick={handleSyncAll}
            disabled={syncing}
          >
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing...' : 'Sync Active Tools'}
          </button>
          <button
            id="licenses-requests-btn"
            className="btn btn-secondary btn-sm"
            onClick={() => setShowRequestsModal(true)}
          >
            <ClipboardList size={14} /> Requests
          </button>
          <button
            id="licenses-add-btn"
            className="btn btn-primary btn-sm"
            onClick={openSubmitModal}
          >
            <Send size={14} /> Submit Request
          </button>
        </div>
      </div>

      {/* Application Quick Tabs */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          marginBottom: 16,
          overflowX: 'auto',
          paddingBottom: 4,
          alignItems: 'center',
        }}
      >
        <button
          className={`btn btn-sm ${filterApp === 'all' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => handleAppTabClick('all')}
        >
          All Applications ({licenses.length})
        </button>

        {appNames.map((name) => {
          const isSelected = filterApp.toLowerCase() === name.toLowerCase();
          const count = licenses.filter((l) => l.application_name === name).length;
          return (
            <button
              key={name}
              className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => handleAppTabClick(name)}
              style={{ display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}
            >
              <ToolLogo name={name} size={15} />
              <span>{name}</span>
              <span
                style={{
                  fontSize: 10,
                  opacity: 0.8,
                  background: isSelected ? 'rgba(255,255,255,0.2)' : 'var(--gray-200)',
                  padding: '1px 5px',
                  borderRadius: 10,
                }}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Filter Toolbar */}
      <div className="toolbar">
        <div className="input-with-icon" style={{ width: 280 }}>
          <span className="input-icon"><Search size={14} /></span>
          <input
            id="licenses-search"
            className="input"
            placeholder="Search licenses, SKUs, categories…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <select
          id="licenses-type-filter"
          className="select"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="all">All License Types</option>
          {licenseTypes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>

        <select
          id="licenses-status-filter"
          className="select"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>

        <div style={{ display: 'flex', gap: 4, background: 'var(--gray-100)', padding: 2, borderRadius: 8 }}>
          <button
            className="btn btn-sm"
            style={{
              padding: '4px 10px',
              fontSize: 12,
              background: viewMode === 'grouped' ? 'white' : 'transparent',
              boxShadow: viewMode === 'grouped' ? 'var(--shadow-sm)' : 'none',
              color: viewMode === 'grouped' ? 'var(--text-primary)' : 'var(--text-muted)',
              border: 'none',
            }}
            onClick={() => setViewMode('grouped')}
          >
            Grouped View
          </button>
          <button
            className="btn btn-sm"
            style={{
              padding: '4px 10px',
              fontSize: 12,
              background: viewMode === 'flat' ? 'white' : 'transparent',
              boxShadow: viewMode === 'flat' ? 'var(--shadow-sm)' : 'none',
              color: viewMode === 'flat' ? 'var(--text-primary)' : 'var(--text-muted)',
              border: 'none',
            }}
            onClick={() => setViewMode('flat')}
          >
            Table View
          </button>
        </div>

        <span className="toolbar-spacer" />
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {filtered.length} licenses found
        </span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<Key size={24} color="var(--gray-400)" />}
          title="No licenses match criteria"
          description="Try resetting your filters or search query."
        />
      ) : viewMode === 'grouped' ? (
        /* ── GROUPED BY APPLICATION VIEW ── */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {Object.entries(groupedByApp).map(([appName, appLicenses]) => {
            return (
              <div
                key={appName}
                className="card"
                style={{
                  overflow: 'hidden',
                  border: '1px solid var(--border-color)',
                  boxShadow: 'var(--shadow-sm)',
                  borderRadius: 16,
                  marginBottom: 20,
                }}
              >
                {/* ── Application Hero Header Banner ── */}
                <AppHeroCard
                  appName={appName}
                  appLicenses={appLicenses}
                  appUserCounts={appUserCounts}
                  onOpenAdminModal={(name) => {
                    const cached = appUserCounts[name];
                    if (cached) {
                      setAppUsersModal({ appName: name, roleFilter: 'admin', users: cached.users });
                    } else {
                      getAppAssignedUsers(name).then((users) => {
                        setAppUsersModal({ appName: name, roleFilter: 'admin', users });
                      });
                    }
                  }}
                  onOpenUsersModal={(name) => {
                    const cached = appUserCounts[name];
                    if (cached) {
                      setAppUsersModal({ appName: name, roleFilter: 'all', users: cached.users });
                    } else {
                      getAppAssignedUsers(name).then((users) => {
                        setAppUsersModal({ appName: name, roleFilter: 'all', users });
                      });
                    }
                  }}
                  onManageLicenses={openSubmitModal}
                />

                {/* ── Licenses Table for this Application ── */}
                {appLicenses.length === 0 ? (
                  <div style={{ padding: '24px 20px', textAlign: 'center', background: 'var(--bg-card)' }}>
                    <Key size={18} color="var(--gray-400)" style={{ marginBottom: 6 }} />
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>
                      0 active licenses registered for {appName}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      Software integration pending activation · 0 seats assigned
                    </div>
                  </div>
                ) : (
                  <div className="table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
                    <table className="table" style={{ margin: 0 }}>
                      <thead>
                        <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                          <th style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.04em', color: 'var(--gray-500)' }}>LICENSE / SKU</th>
                          <th style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.04em', color: 'var(--gray-500)' }}>CATEGORY</th>
                          <th style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.04em', color: 'var(--gray-500)' }}>ASSIGNED SEATS</th>
                          <th style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.04em', color: 'var(--gray-500)' }}>UTILIZATION</th>
                          <th style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.04em', color: 'var(--gray-500)' }}>EXPIRY DATE</th>
                          <th style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.04em', color: 'var(--gray-500)' }}>STATUS</th>
                          <th style={{ textAlign: 'right', textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.04em', color: 'var(--gray-500)' }}>ACTIONS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {appLicenses.map((lic) => {
                          const total = lic.total_quantity || 0;
                          const assigned = lic.allocated_quantity || lic.used_quantity || 0;
                          const available = Math.max(0, total - assigned);
                          const utilPct = total ? Math.min(100, Math.round((assigned / total) * 100)) : 0;
                          const IconComponent = CATEGORY_ICONS[lic.license_type] || Key;

                          // Utilization Bar Color Logic matching template image
                          const getBarColor = (pct) => {
                            if (pct >= 95) return '#ef4444'; // Red for 100%
                            if (pct >= 75) return '#f97316'; // Orange for ~80%
                            if (pct > 0) return '#2563eb';   // Blue
                            return '#cbd5e1';               // Gray for 0%
                          };
                          const barColor = getBarColor(utilPct);

                          return (
                            <tr
                              key={lic.license_id}
                              style={{ cursor: 'pointer' }}
                              onClick={() => setSelectedLicense(lic)}
                              className="license-row-clickable"
                            >
                              <td>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                  <div
                                    style={{
                                      width: 32,
                                      height: 32,
                                      borderRadius: 8,
                                      background: '#f1f5f9',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      flexShrink: 0,
                                    }}
                                  >
                                    <ToolLogo name={lic.application_name} size={20} />
                                  </div>
                                  <div>
                                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--gray-900)' }}>
                                      {lic.license_name}
                                    </div>
                                    <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace', textTransform: 'uppercase' }}>
                                      {lic.raw_sku_part_number || lic.product_code || '—'}
                                    </div>
                                  </div>
                                </div>
                              </td>
                              <td>
                                <span style={{ fontSize: 12, fontWeight: 500, color: '#334155' }}>
                                  {lic.license_type || 'Commercial'}
                                </span>
                              </td>
                              <td>
                                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--gray-900)' }}>
                                  {formatNumber(assigned)} <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>/ {formatNumber(total)}</span>
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                  {formatNumber(available)} available
                                </div>
                              </td>
                              <td style={{ minWidth: 140 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--gray-800)', minWidth: 38 }}>
                                    {utilPct}%
                                  </span>
                                  <div style={{ flex: 1, height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
                                    <div
                                      style={{
                                        height: '100%',
                                        width: `${utilPct}%`,
                                        background: barColor,
                                        borderRadius: 3,
                                      }}
                                    />
                                  </div>
                                </div>
                              </td>
                              <td>
                                <div style={{ fontSize: 12, color: 'var(--gray-800)', fontWeight: 500 }}>
                                  {formatDate(lic.expiry_date)}
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                  {lic.auto_renew ? 'Auto-renews' : 'Manual renewal'}
                                </div>
                              </td>
                              <td>
                                <Badge variant={lic.status === 'active' ? 'success' : 'neutral'}>
                                  {capitalize(lic.status)}
                                </Badge>
                              </td>
                              <td style={{ textAlign: 'right' }}>
                                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                                  <button
                                    className="btn btn-secondary btn-sm"
                                    style={{
                                      borderRadius: 6,
                                      fontSize: 12,
                                      padding: '4px 12px',
                                      fontWeight: 500,
                                      background: 'white',
                                      border: '1px solid var(--border-color)',
                                    }}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSelectedLicense(lic);
                                    }}
                                  >
                                    View Users
                                  </button>
                                  <button
                                    className="btn btn-icon btn-sm"
                                    style={{ color: 'var(--gray-400)', padding: 4 }}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSelectedLicense(lic);
                                    }}
                                    title="More options"
                                  >
                                    <MoreVertical size={15} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        /* ── FLAT TABLE VIEW ── */
        <div className="table-wrapper">
          <table className="table" id="licenses-table">
            <thead>
              <tr>
                <th>License / Product</th>
                <th>Application</th>
                <th>Category / Type</th>
                <th>Assigned Seats</th>
                <th>Utilization</th>
                <th>Expiry Date</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Assigned Users</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((lic) => {
                const utilPct = lic.total_quantity
                  ? Math.min(100, Math.round(((lic.allocated_quantity || lic.used_quantity || 0) / lic.total_quantity) * 100))
                  : 0;
                const utilLevel = getUtilizationLevel(utilPct);
                const IconComponent = CATEGORY_ICONS[lic.license_type] || Key;

                return (
                  <tr
                    key={lic.license_id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelectedLicense(lic)}
                    id={`license-row-${lic.license_id}`}
                  >
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div
                          style={{
                            padding: 6,
                            borderRadius: 6,
                            background: 'var(--gray-100)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          <IconComponent size={15} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, color: 'var(--gray-900)' }}>{lic.license_name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                            {lic.raw_sku_part_number || lic.product_code}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <ToolLogo name={lic.application_name} size={18} />
                        <span style={{ fontSize: 13, fontWeight: 500 }}>{lic.application_name}</span>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--gray-700)' }}>
                        {lic.license_type}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>
                        {formatNumber(lic.allocated_quantity || lic.used_quantity)}
                        <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>
                          {' '}/ {formatNumber(lic.total_quantity)}
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {formatNumber(lic.available_quantity)} available
                      </div>
                    </td>
                    <td style={{ minWidth: 120 }}>
                      <div className="flex-between" style={{ marginBottom: 4 }}>
                        <span style={{ fontSize: 11, fontWeight: 600 }}>{utilPct}%</span>
                      </div>
                      <ProgressBar value={utilPct} max={100} variant={utilLevel} />
                    </td>
                    <td>
                      <div style={{ fontSize: 12 }}>{formatDate(lic.expiry_date)}</div>
                    </td>
                    <td>
                      <Badge variant={lic.status === 'active' ? 'success' : 'neutral'}>
                        {capitalize(lic.status)}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedLicense(lic);
                        }}
                      >
                        <Users size={13} />
                        <span>Show Users</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* License Assigned Users Modal */}
      <LicenseUsersModal
        open={!!selectedLicense}
        license={selectedLicense}
        onClose={() => setSelectedLicense(null)}
      />

      {/* App Users Modal (Admin / Users tiles) */}
      <AppUsersModal
        open={!!appUsersModal}
        appName={appUsersModal?.appName}
        roleFilter={appUsersModal?.roleFilter}
        users={appUsersModal?.users || []}
        onClose={() => setAppUsersModal(null)}
      />

      {/* Submit Request Modal — IT Team raises a license request for a user */}
      <Modal
        open={showSubmitModal}
        title="Submit License Request"
        onClose={() => setShowSubmitModal(false)}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowSubmitModal(false)}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleSubmitRequest}
              disabled={submitting}
              id="submit-request-confirm-btn"
            >
              {submitting ? 'Submitting…' : 'Submit Request'}
            </button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ fontSize: 12, color: 'var(--text-muted, #64748b)', margin: 0 }}>
            Flow: <b>IT Team</b> → <b>Tower Head</b> (email approval) →
            <b> Application Owner</b> (email approval) → <b>IT Team</b> (final action).
            Approvers receive an approval link by email — track progress under “Requests”.
          </p>

          <div style={{ fontWeight: 700, fontSize: 12, textTransform: 'uppercase', color: '#94a3b8', marginTop: 4 }}>
            For the user
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label className="label">Requested For (Full Name) *</label>
              <input
                className="input"
                placeholder="e.g. Jane Smith"
                value={newReq.requested_for}
                onChange={(e) => setNewReq((r) => ({ ...r, requested_for: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">User Email *</label>
              <input
                className="input"
                type="email"
                placeholder="jane.smith@company.com"
                value={newReq.requested_for_email}
                onChange={(e) => setNewReq((r) => ({ ...r, requested_for_email: e.target.value }))}
              />
            </div>
          </div>

          <div>
            <label className="label">License / Product Name *</label>
            <input
              className="input"
              placeholder="e.g. Zoom Enterprise One"
              value={newReq.license_name}
              onChange={(e) => setNewReq((r) => ({ ...r, license_name: e.target.value }))}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label className="label">Application</label>
              <select
                className="select"
                value={newReq.application_name}
                onChange={(e) =>
                  setNewReq((r) => ({ ...r, application_name: e.target.value }))
                }
                style={{ width: '100%' }}
              >
                <option value="Microsoft 365">Microsoft 365</option>
                <option value="Slack">Slack</option>
                <option value="Lucidchart">Lucidchart</option>
                <option value="Box">Box</option>
                <option value="Zoom">Zoom</option>
                <option value="Sofia - (Pilot)">Sofia - (Pilot)</option>
                <option value="_Jira">_Jira</option>
                <option value="CATO">CATO</option>
              </select>
            </div>
            <div>
              <label className="label">License Type</label>
              <input
                className="input"
                placeholder="e.g. Business Suite"
                value={newReq.license_type}
                onChange={(e) => setNewReq((r) => ({ ...r, license_type: e.target.value }))}
              />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <div>
              <label className="label">Request Type</label>
              <select
                className="select"
                value={newReq.request_type}
                onChange={(e) => setNewReq((r) => ({ ...r, request_type: e.target.value }))}
                style={{ width: '100%' }}
              >
                <option value="New License">New License</option>
                <option value="Additional Seats">Additional Seats</option>
                <option value="Upgrade">Upgrade</option>
                <option value="Renewal">Renewal</option>
              </select>
            </div>
            <div>
              <label className="label">Quantity</label>
              <input
                type="number"
                min="1"
                className="input"
                value={newReq.quantity}
                onChange={(e) => setNewReq((r) => ({ ...r, quantity: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Priority</label>
              <select
                className="select"
                value={newReq.priority}
                onChange={(e) => setNewReq((r) => ({ ...r, priority: e.target.value }))}
                style={{ width: '100%' }}
              >
                <option value="Low">Low</option>
                <option value="Normal">Normal</option>
                <option value="High">High</option>
                <option value="Critical">Critical</option>
              </select>
            </div>
          </div>
          <div>
            <label className="label">Justification / Business Reason</label>
            <textarea
              className="input"
              rows={2}
              placeholder="Why is this license needed?"
              value={newReq.justification}
              onChange={(e) => setNewReq((r) => ({ ...r, justification: e.target.value }))}
              style={{ resize: 'vertical' }}
            />
          </div>
          <div style={{ fontWeight: 700, fontSize: 12, textTransform: 'uppercase', color: '#94a3b8', marginTop: 4 }}>
            Approvers (receive approval emails)
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label className="label">Tower Head Name *</label>
              <input
                className="input"
                placeholder="e.g. Ravi Kumar"
                value={newReq.tower_head_name}
                onChange={(e) => setNewReq((r) => ({ ...r, tower_head_name: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Tower Head Email *</label>
              <input
                className="input"
                type="email"
                placeholder="tower.head@company.com"
                value={newReq.tower_head_email}
                onChange={(e) => setNewReq((r) => ({ ...r, tower_head_email: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Application Owner Name *</label>
              <input
                className="input"
                placeholder="e.g. Anita Rao"
                value={newReq.app_owner_name}
                onChange={(e) => setNewReq((r) => ({ ...r, app_owner_name: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Application Owner Email *</label>
              <input
                className="input"
                type="email"
                placeholder="app.owner@company.com"
                value={newReq.app_owner_email}
                onChange={(e) => setNewReq((r) => ({ ...r, app_owner_email: e.target.value }))}
              />
            </div>
          </div>

          <div style={{ fontSize: 12, color: 'var(--text-muted, #64748b)' }}>
            Raised by: <b>{user?.name || 'IT Team'}</b> ({user?.email || 'no email'})
          </div>
        </div>
      </Modal>

      {/* Requests Modal — approval pipeline (whose approval is pending) */}
      <Modal
        open={showRequestsModal}
        title="License Requests — Approval Flow"
        onClose={() => {
          setShowRequestsModal(false);
          setSelectedRequest(null);
        }}
        footer={
          <button
            className="btn btn-secondary"
            onClick={() => {
              setShowRequestsModal(false);
              setSelectedRequest(null);
            }}
          >
            Close
          </button>
        }
      >
        {requestsLoading ? (
          <Spinner size={28} />
        ) : selectedRequest ? (
          <RequestPipeline
            req={selectedRequest}
            onBack={() => setSelectedRequest(null)}
            onFinalAction={handleFinalAction}
          />
        ) : requests.length === 0 ? (
          <EmptyState
            icon={<ClipboardList size={26} />}
            title="No requests yet"
            description="Use “Submit Request” to raise a license request for a user."
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {requests.map((r) => (
              <button
                key={r.request_id}
                onClick={() => setSelectedRequest(r)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '10px 12px', borderRadius: 8, cursor: 'pointer',
                  border: '1px solid var(--border-color, #e2e8f0)',
                  background: 'var(--bg-card, #fff)', textAlign: 'left',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{r.request_id}</div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>
                    {r.license_name} · {r.application_name} · for {r.requested_for}
                  </div>
                </div>
                <RequestStatusBadge status={r.status} label={r.status_label} />
                <ChevronRight size={16} color="#94a3b8" />
              </button>
            ))}
          </div>
        )}
      </Modal>

      {/* App-Level Users Modal (Admin / Users Tiles) */}
      <AppUsersModal
        open={!!appUsersModal}
        appName={appUsersModal?.appName}
        roleFilter={appUsersModal?.roleFilter}
        users={appUsersModal?.users || []}
        onClose={() => setAppUsersModal(null)}
      />
    </>
  );
};

export default LicensesPage;
