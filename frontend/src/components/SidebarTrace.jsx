export default function SidebarTrace({ activeStep, doneSteps }) {
  const steps = [
    { id: 'plan', label: '01 — Plan', desc: 'decompose query' },
    { id: 'approval', label: '02 — Review', desc: 'human approval' },
    { id: 'research', label: '03 — Research', desc: 'parallel search + summarize' },
    { id: 'critique', label: '04 — Critique', desc: 'check for gaps' },
    { id: 'synthesize', label: '05 — Synthesize', desc: 'final cited report' },
  ];

  return (
    <aside className="trace-container">
      {steps.map(step => {
        const isActive = activeStep === step.id;
        const isDone = doneSteps.includes(step.id);
        
        let statusClass = '';
        if (isActive) statusClass = 'active';
        else if (isDone) statusClass = 'done';

        return (
          <div key={step.id} className={`trace-step ${statusClass}`}>
            <div className="trace-indicator"></div>
            <div className="trace-label">{step.label}</div>
            <div className="trace-desc">{step.desc}</div>
          </div>
        );
      })}
    </aside>
  );
}
