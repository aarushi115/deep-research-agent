import { useState } from 'react';

export default function ResearchForm({ onSubmit, isRunning }) {
  const [query, setQuery] = useState('');
  const [hitl, setHitl] = useState(true);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSubmit(query, hitl);
  };

  return (
    <form className="query-form" onSubmit={handleSubmit}>
      <div className="input-group">
        <label htmlFor="query">Research Query</label>
        <textarea
          id="query"
          rows={3}
          placeholder="e.g. What are the trade-offs between LangGraph and CrewAI for production multi-agent systems?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={isRunning}
          required
        />
      </div>
      
      <div className="checkbox-group">
        <input 
          type="checkbox" 
          id="hitl" 
          checked={hitl} 
          onChange={(e) => setHitl(e.target.checked)}
          disabled={isRunning}
        />
        <label htmlFor="hitl">Require human approval of the research plan</label>
      </div>

      <div style={{ marginTop: '8px' }}>
        <button type="submit" className="btn-primary" disabled={isRunning || !query.trim()}>
          {isRunning ? 'Investigation in Progress...' : 'Open Investigation'}
        </button>
      </div>
    </form>
  );
}
