import { downloadReportPdf } from '../utils/pdfExport';

export default function FinalReport({ report }) {
  if (!report) return null;

  return (
    <div className="report-container">
      <div className="glass-panel" style={{ padding: '48px' }}>
        <div className="report-header">
          <h2 className="report-title">{report.title}</h2>
          <button
            type="button"
            className="btn-secondary report-download-btn"
            onClick={() => downloadReportPdf(report)}
          >
            Download PDF
          </button>
        </div>
        <div className="report-summary">{report.executive_summary}</div>
        
        {report.sections?.map((section, idx) => (
          <div key={idx} className="report-section">
            <h3>{section.heading}</h3>
            <p>{section.body}</p>
          </div>
        ))}
        
        {report.citations?.length > 0 && (
          <div className="report-section" style={{ marginTop: '48px', borderTop: '1px solid var(--border-color)', paddingTop: '32px' }}>
            <h3>Citations & Sources</h3>
            <ul className="citations-list">
              {report.citations.map((c, idx) => (
                <li key={idx} className="citation-item">
                  <span style={{ color: 'var(--text-primary)' }}>{c.claim}</span> — <a href={c.source_url} target="_blank" rel="noopener noreferrer">{c.source_url}</a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {report.open_questions?.length > 0 && (
          <div className="open-questions">
            <h3>Open Questions</h3>
            <ul style={{ paddingLeft: '20px', color: 'var(--text-primary)' }}>
              {report.open_questions.map((q, idx) => (
                <li key={idx} style={{ marginBottom: '8px' }}>{q}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
