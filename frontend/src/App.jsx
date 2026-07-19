import { useState, useEffect } from 'react';
import SidebarTrace from './components/SidebarTrace';
import ResearchForm from './components/ResearchForm';
import ApprovalCard from './components/ApprovalCard';
import FinalReport from './components/FinalReport';
import './index.css';

const API_BASE = 'http://localhost:8001/api';

function App() {
  const [threadId, setThreadId] = useState(null);
  const [jobState, setJobState] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let timer;
    if (isPolling && threadId) {
      timer = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/research/${threadId}`);
          if (!res.ok) throw new Error(`Status check failed (${res.status})`);
          const data = await res.json();
          setJobState(data);
          
          if (data.status === 'completed' || data.status === 'error') {
            setIsPolling(false);
          }
        } catch (err) {
          setError(err.message);
          setIsPolling(false);
        }
      }, 1500);
    }
    return () => clearInterval(timer);
  }, [isPolling, threadId]);

  const startInvestigation = async (query, hitlEnabled) => {
    setError(null);
    setJobState(null);
    try {
      const res = await fetch(`${API_BASE}/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, hitl_enabled: hitlEnabled }),
      });
      if (!res.ok) throw new Error(`Failed to start (${res.status})`);
      const data = await res.json();
      setThreadId(data.thread_id);
      setIsPolling(true);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleApproval = async (approved, feedback) => {
    try {
      const res = await fetch(`${API_BASE}/research/${threadId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved, feedback }),
      });
      if (!res.ok) throw new Error(`Approval failed (${res.status})`);
      setIsPolling(true);
      // Optimistically update status so approval box hides immediately
      setJobState(prev => ({ ...prev, status: 'running' }));
    } catch (err) {
      setError(err.message);
    }
  };

  const determineDoneSteps = () => {
    if (!jobState) return [];
    const done = [];
    if (jobState.sub_questions && jobState.sub_questions.length) done.push('plan');
    if (jobState.status !== 'waiting_approval' && jobState.sub_questions?.length) done.push('approval');
    if (jobState.research_results && jobState.research_results.length > 0) done.push('research');
    if (jobState.status === 'completed') done.push('critique', 'synthesize');
    return done;
  };

  const determineActiveStep = () => {
    if (!jobState) return null;
    const hasResults = jobState.research_results && jobState.research_results.length > 0;
    
    if (jobState.status === 'waiting_approval') return 'approval';
    if (jobState.status === 'running') {
      return hasResults ? 'critique' : (determineDoneSteps().includes('plan') ? 'research' : 'plan');
    }
    if (jobState.status === 'completed') return 'synthesize';
    return null;
  };

  return (
    <div className="app-container">
      <header>
        <div>
          <h1>Deep Research Agent</h1>
        </div>
        {threadId && (
          <div className="case-id">
            CASE FILE #{threadId.slice(0, 8).toUpperCase()}
          </div>
        )}
      </header>

      <SidebarTrace activeStep={determineActiveStep()} doneSteps={determineDoneSteps()} />

      <main>
        <div className="glass-panel">
          <ResearchForm onSubmit={startInvestigation} isRunning={isPolling || jobState?.status === 'waiting_approval'} />
          
          {error && <div className="error-message">{error}</div>}
          
          {jobState?.status_message && (
            <div className="status-indicator">
              {jobState.status_message}
            </div>
          )}

          {jobState?.sub_questions?.length > 0 && (
            <div style={{ marginTop: '24px' }}>
              <label>Identified Sub-Questions</label>
              <ul className="subq-list">
                {jobState.sub_questions.map((sq, i) => (
                  <li key={i} className="subq-item">
                    <div className="subq-question">{sq.question}</div>
                    <div className="subq-rationale">{sq.rationale}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {jobState?.status === 'waiting_approval' && (
            <ApprovalCard onApprove={(feedback) => handleApproval(true, feedback)} onReject={(feedback) => handleApproval(false, feedback)} />
          )}
        </div>

        {jobState?.status === 'completed' && jobState.report && (
          <FinalReport report={jobState.report} />
        )}
      </main>
    </div>
  );
}

export default App;
