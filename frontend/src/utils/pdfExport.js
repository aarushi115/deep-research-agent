import { jsPDF } from 'jspdf';

const MARGIN = 20;
const PAGE_WIDTH = 210;
const PAGE_HEIGHT = 297;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2;

function slugify(text) {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 60) || 'research-report'
  );
}

function createPdfWriter(doc) {
  let y = MARGIN;

  const ensureSpace = (needed) => {
    if (y + needed > PAGE_HEIGHT - MARGIN) {
      doc.addPage();
      y = MARGIN;
    }
  };

  const writeBlock = (text, { fontSize = 11, style = 'normal', spacing = 6 } = {}) => {
    if (!text?.trim()) return;

    doc.setFontSize(fontSize);
    doc.setFont('helvetica', style);
    const lineHeight = fontSize * 0.45;
    const lines = doc.splitTextToSize(text.trim(), CONTENT_WIDTH);

    for (const line of lines) {
      ensureSpace(lineHeight);
      doc.text(line, MARGIN, y);
      y += lineHeight;
    }
    y += spacing;
  };

  return { writeBlock };
}

export function downloadReportPdf(report) {
  if (!report) return;

  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const { writeBlock } = createPdfWriter(doc);

  writeBlock(report.title, { fontSize: 20, style: 'bold', spacing: 10 });
  writeBlock('Executive Summary', { fontSize: 14, style: 'bold', spacing: 4 });
  writeBlock(report.executive_summary);

  for (const section of report.sections || []) {
    writeBlock(section.heading, { fontSize: 14, style: 'bold', spacing: 4 });
    writeBlock(section.body);
  }

  if (report.citations?.length) {
    writeBlock('Citations & Sources', { fontSize: 14, style: 'bold', spacing: 4 });
    for (const citation of report.citations) {
      writeBlock(`${citation.claim} — ${citation.source_url}`, { fontSize: 10, spacing: 3 });
    }
  }

  if (report.open_questions?.length) {
    writeBlock('Open Questions', { fontSize: 14, style: 'bold', spacing: 4 });
    for (const question of report.open_questions) {
      writeBlock(`• ${question}`, { fontSize: 11, spacing: 3 });
    }
  }

  doc.save(`${slugify(report.title)}.pdf`);
}
