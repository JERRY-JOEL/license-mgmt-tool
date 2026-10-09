import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { CheckCircle, XCircle, Clock, ShieldCheck } from 'lucide-react';
import { Spinner, AlertBanner, Badge } from '../components/ui';
import { getApprovalByToken, submitApprovalDecision } from '../api/services';

/**
 * Public approval page reached from the Approve/Decline buttons in the
 * approval email: /approvals/:token  (token-based, no portal login needed).
 */
const ApprovalPage = () => {
  const { token } = useParams();
  const [searchParams] = useSearchParams();
  const preselectedAction = searchParams.get('action'); // 'approve' | 'reject'

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null); // response after deciding

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApprovalByToken(token);
        if (alive) setData(res.data);
      } catch (err) {
        if (alive) {
          setError(
            err?.response?.data?.detail
            || 'This approval link is invalid or has expired.'
          );
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [token]);

  const decide = async (action) => {
    setSubmitting(true);
    setError('');
    try {
      const res = await submitApprovalDecision(token, action, comment || null);
      setResult(res.data);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not record your decision.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="login-page">
        <div className="login-card" style={{ textAlign: 'center' }}>
          <Spinner size={32} />
          <p style={{ fontSize: 13, color: '#64748b', marginTop: 12 }}>
            Loading approval…
          </p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-logo">
            <div className="login-logo-icon">LM</div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>LicenseHub</div>
          </div>
          <AlertBanner type="error" message={error} />
          <p style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center' }}>
            Ask the IT Team to resend the approval email if the link no longer works.
          </p>
        </div>
      </div>
    );
  }

  const req = data.request;

  // After the decision is recorded
  if (result) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div style={{ textAlign: 'center', padding: '10px 0 4px' }}>
            <CheckCircle size={40} color="#16a34a" />
            <h1 style={{ fontSize: 20, margin: '10px 0 4px' }}>
              {result.your_action === 'approve' ? 'Approval recorded' : 'Rejection recorded'}
            </h1>
            <p style={{ fontSize: 13, color: '#64748b' }}>{result.message}</p>
          </div>
          <div
            style={{
              marginTop: 14, padding: '12px 14px', borderRadius: 8,
              background: '#f8fafc', border: '1px solid #e2e8f0', fontSize: 13,
            }}
          >
            <div><b>Request:</b> {req.request_id}</div>
            <div><b>License:</b> {req.license_name} · {req.application_name}</div>
            <div><b>Requested For:</b> {req.requested_for}</div>
            <div style={{ marginTop: 6 }}>
              <b>Status:</b> {req.status_label}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-card" style={{ maxWidth: 560 }}>
        <div className="login-logo">
          <div className="login-logo-icon">LM</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>LicenseHub</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              License Request Approval
            </div>
          </div>
        </div>

        {error && <AlertBanner type="error" message={error} />}

        {/* Who is acting */}
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px',
            borderRadius: 8, background: '#eff6ff', border: '1px solid #bfdbfe',
            marginBottom: 14, fontSize: 13, color: '#1e40af',
          }}
        >
          <ShieldCheck size={16} />
          You are approving as <b>{data.your_role}</b>
          {data.already_actioned && (
            <Badge variant="success">already {data.your_action}d</Badge>
          )}
          {data.expired && !data.already_actioned && (
            <Badge variant="neutral">request closed</Badge>
          )}
        </div>

        <h1 style={{ fontSize: 18, margin: '0 0 8px' }}>{req.request_id}</h1>

        {/* Request details */}
        <div
          style={{
            fontSize: 13, borderRadius: 8, border: '1px solid #e2e8f0',
            overflow: 'hidden', marginBottom: 14,
          }}
        >
          {[
            ['Application', req.application_name],
            ['License / Product', req.license_name],
            ['License Type', req.license_type || '—'],
            ['Request Type', req.request_type],
            ['Quantity', req.quantity],
            ['Priority', req.priority],
            ['Requested For', `${req.requested_for} (${req.requested_for_email})`],
            ['Raised By', `${req.submitted_by || 'IT Team'} (${req.submitted_by_email || '—'})`],
            ['Justification', req.justification || '—'],
            ['Status', req.status_label],
          ].map(([k, v]) => (
            <div
              key={k}
              style={{
                display: 'flex', gap: 10, padding: '8px 12px',
                borderTop: '1px solid #f1f5f9',
              }}
            >
              <span style={{ minWidth: 130, fontWeight: 600, color: '#334155' }}>{k}</span>
              <span style={{ color: '#475569', wordBreak: 'break-word' }}>{v}</span>
            </div>
          ))}
        </div>

        {data.already_actioned || data.expired ? (
          <div
            style={{
              padding: '12px 14px', borderRadius: 8, fontSize: 13,
              background: data.already_actioned ? '#f0fdf4' : '#f1f5f9',
              border: `1px solid ${data.already_actioned ? '#bbf7d0' : '#e2e8f0'}`,
              color: '#334155', textAlign: 'center',
            }}
          >
            {data.already_actioned
              ? `You already ${data.your_action}d this request — no further action needed.`
              : 'This request is already closed — no further action needed.'}
          </div>
        ) : (
          <>
            <label className="label" htmlFor="approval-comment">Comment (optional)</label>
            <textarea
              id="approval-comment"
              className="input"
              rows={2}
              placeholder="Any conditions or notes…"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              style={{ resize: 'vertical', marginBottom: 12 }}
            />
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                className="btn btn-secondary"
                style={{ flex: 1 }}
                disabled={submitting}
                onClick={() => decide('reject')}
                id="approval-reject-btn"
              >
                <XCircle size={16} /> Decline
              </button>
              <button
                className="btn btn-primary"
                style={{ flex: 1 }}
                disabled={submitting}
                onClick={() => decide('approve')}
                id="approval-approve-btn"
              >
                <CheckCircle size={16} />
                {submitting ? 'Recording…' : 'Approve'}
              </button>
            </div>
          </>
        )}

        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center',
            marginTop: 16, fontSize: 11, color: '#94a3b8',
          }}
        >
          <Clock size={12} /> Secure token link — no portal login required.
          {preselectedAction === 'reject' && ' Tip: choose Decline below.'}
        </div>
      </div>
    </div>
  );
};

export default ApprovalPage;
