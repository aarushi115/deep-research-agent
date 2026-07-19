import { downloadReportPdf } from '../utils/pdfExport';

const formatText = (text) => {
  if (!text) return null;
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  
  // Split the text by double newlines to create separate paragraphs for better spacing
  return text.split(/\n\n+/).map((paragraph, pIdx) => {
    const parts = paragraph.split(urlRegex);
    return (
      <p key={pIdx} style={{ marginBottom: '1.5em', lineHeight: '1.8' }}>
        {parts.map((part, i) => {
          if (part.match(urlRegex)) {
            return (
              <a 
                key={i} 
                href={part} 
                target="_blank" 
                rel="noopener noreferrer"
                style={{ color: 'var(--accent-primary)', textDecoration: 'underline' }}
              >
                {part}
              </a>
            );
          }
          return part;
        })}
      </p>
    );
  });
};

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
        <div className="report-summary">{formatText(report.executive_summary)}</div>
        
        {report.sections?.map((section, idx) => (
          <div key={idx} className="report-section" style={{ marginTop: '40px' }}>
            <h3 style={{ marginBottom: '24px', fontSize: '24px' }}>{section.heading}</h3>
            {formatText(section.body)}
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
