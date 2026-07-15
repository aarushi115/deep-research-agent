import { useState } from 'react';

export default function ApprovalCard({ onApprove, onReject }) {
  const [feedback, setFeedback] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleApprove = () => {
    setIsSubmitting(true);
    onApprove(feedback);
  };

  const handleReject = () => {
    setIsSubmitting(true);
    onReject(feedback);
  };

  return (
    <div className="approval-card">
      <h3 style={{ color: 'var(--text-accent)', marginBottom: '8px', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
        Reviewer Decision Required
      </h3>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', fontSize: '14px' }}>
        Approve this plan to dispatch parallel researchers, or reject with feedback to have it refined.
      </p>
      
      <div className="input-group">
        <textarea
          rows={2}
          placeholder="Optional feedback if rejecting..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={isSubmitting}
        />
      </div>

      <div className="approval-actions">
        <button 
          className="btn-primary" 
          onClick={handleApprove} 
          disabled={isSubmitting}
        >
          Approve Plan
        </button>
        <button 
          className="btn-secondary" 
          onClick={handleReject}
          disabled={isSubmitting}
        >
          Reject & Refine
        </button>
      </div>
    </div>
  );
}
