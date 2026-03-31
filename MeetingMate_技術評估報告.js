const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageNumber, PageBreak, LevelFormat } = require("docx");

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerBorder = { style: BorderStyle.SINGLE, size: 1, color: "2E5B8A" };
const headerBorders = { top: headerBorder, bottom: headerBorder, left: headerBorder, right: headerBorder };

function headerCell(text, width) {
  return new TableCell({
    borders: headerBorders, width: { size: width, type: WidthType.DXA },
    shading: { fill: "2E5B8A", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, color: "FFFFFF", font: "Arial", size: 20 })] })]
  });
}

function cell(text, width, opts = {}) {
  const runs = text.split("\n").reduce((acc, line, i) => {
    if (i > 0) acc.push(new TextRun({ break: 1, font: "Arial", size: 20 }));
    acc.push(new TextRun({ text: line, font: "Arial", size: 20, bold: opts.bold, color: opts.color }));
    return acc;
  }, []);
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: runs })]
  });
}

function heading(text, level) {
  return new Paragraph({ heading: level, spacing: { before: 300, after: 150 },
    children: [new TextRun({ text, font: "Arial" })] });
}

function para(text, opts = {}) {
  const runs = text.split("\n").reduce((acc, line, i) => {
    if (i > 0) acc.push(new TextRun({ break: 1, font: "Arial", size: 22 }));
    acc.push(new TextRun({ text: line, font: "Arial", size: 22, bold: opts.bold, color: opts.color, italics: opts.italics }));
    return acc;
  }, []);
  return new Paragraph({ spacing: { after: 120 }, children: runs });
}

function bullet(text, ref, level = 0) {
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22 })]
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "1A3A5C" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2E5B8A" },
        paragraph: { spacing: { before: 280, after: 150 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "3D7AB5" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "\u25E6", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
      ]},
      { reference: "nums", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
      { reference: "recs", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "2E5B8A", space: 4 } },
          children: [new TextRun({ text: "MeetingMate \u6280\u8853\u8a55\u4f30\u5831\u544a", font: "Arial", size: 18, color: "888888", italics: true })]
        })
      ]})
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 2, color: "CCCCCC", space: 4 } },
          children: [
            new TextRun({ text: "Page ", font: "Arial", size: 18, color: "888888" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "888888" }),
          ]
        })
      ]})
    },
    children: [
      // ─── Title ───
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 },
        children: [new TextRun({ text: "MeetingMate", font: "Arial", size: 52, bold: true, color: "1A3A5C" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
        children: [new TextRun({ text: "\u8a9e\u97f3\u8f49\u6587\u5b57\u8207\u5373\u6642\u7ffb\u8b6f\u6280\u8853\u8a55\u4f30\u5831\u544a", font: "Arial", size: 32, color: "2E5B8A" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
        children: [new TextRun({ text: "2026\u5e743\u670830\u65e5", font: "Arial", size: 22, color: "888888" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2E5B8A", space: 8 } },
        children: [new TextRun({ text: "\u9700\u6c42\uff1a\u5373\u6642\u8a9e\u97f3\u8f49\u6587\u5b57\uff08\u542b\u82f1\u8b6f\u4e2d\uff09+ \u5373\u6642\u91cd\u9ede\u6458\u8981 + \u96e2\u7dda\u6703\u8b70\u8a18\u9304\u8207\u7ffb\u8b6f", font: "Arial", size: 22, color: "555555", italics: true })] }),

      // ─── Section 1: Background ───
      heading("\u4e00\u3001\u8a55\u4f30\u80cc\u666f\u8207\u76ee\u6a19", HeadingLevel.HEADING_1),
      para("MeetingMate \u76ee\u524d\u5df2\u5be6\u73fe\u96e2\u7dda\u9304\u97f3\u6a94\u7684\u8a9e\u97f3\u8f49\u6587\u5b57\uff08WhisperX + pyannote speaker diarization\uff09\u3001LLM \u6703\u8b70\u6458\u8981\u3001\u8207 Google Drive \u5099\u4efd\u529f\u80fd\u3002\u73fe\u5728\u5e0c\u671b\u64f4\u5c55\u5169\u5927\u529f\u80fd\uff1a"),
      bullet("\u529f\u80fd A\uff1a\u5373\u6642\u8a9e\u97f3\u8f49\u6587\u5b57\uff08Real-time STT\uff09\u2014\u2014 \u542b\u82f1\u6587\u5373\u6642\u7ffb\u8b6f\u6210\u4e2d\u6587\uff0c\u4ee5\u53ca\u5373\u6642\u91cd\u9ede\u6458\u8981", "bullets"),
      bullet("\u529f\u80fd B\uff1a\u9304\u97f3\u6a94\u7ffb\u8b6f\uff08Batch Translation\uff09\u2014\u2014 \u5c07\u82f1\u6587\u9304\u97f3\u6a94\u8f49\u9304\u5f8c\u7ffb\u8b6f\u6210\u4e2d\u6587", "bullets"),

      // ─── Section 2: Technology Landscape ───
      heading("\u4e8c\u3001\u6280\u8853\u65b9\u6848\u7e3d\u89bd", HeadingLevel.HEADING_1),

      heading("2.1 Microsoft VibeVoice-ASR", HeadingLevel.HEADING_2),
      para("2026\u5e741\u670821\u65e5\u7531\u5fae\u8edf\u958b\u6e90\uff0c\u662f\u4e00\u500b 9B \u53c3\u6578\u7684\u7d71\u4e00\u8a9e\u97f3\u8fa8\u8b58\u6a21\u578b\uff0c\u53ef\u5728\u55ae\u6b21\u63a8\u8ad6\u4e2d\u8655\u7406\u9577\u9054 60 \u5206\u9418\u7684\u97f3\u8a0a\u3002"),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 6560],
        rows: [
          new TableRow({ children: [headerCell("\u7279\u6027", 2800), headerCell("\u8aaa\u660e", 6560)] }),
          new TableRow({ children: [cell("\u6a21\u578b\u5927\u5c0f", 2800, { bold: true }), cell("9B \u53c3\u6578\uff0c\u9700 GPU\uff08\u5efa\u8b70 24GB+ VRAM\uff09", 6560)] }),
          new TableRow({ children: [cell("\u6838\u5fc3\u529f\u80fd", 2800, { bold: true }), cell("ASR + Speaker Diarization + Timestamping \u4e09\u5408\u4e00\n\u55ae\u6b21\u63a8\u8ad6\u540c\u6642\u8f38\u51fa\u300c\u8ab0\u8aaa\u7684\u300d\u300c\u4ec0\u9ebc\u6642\u5019\u300d\u300c\u8aaa\u4e86\u4ec0\u9ebc\u300d", 6560)] }),
          new TableRow({ children: [cell("\u8a9e\u8a00\u652f\u63f4", 2800, { bold: true }), cell("50+ \u8a9e\u8a00\uff0c\u539f\u751f\u652f\u63f4\u4e2d\u82f1\u6587 code-switching", 6560)] }),
          new TableRow({ children: [cell("\u4e2d\u6587\u8868\u73fe", 2800, { bold: true }), cell("\u5728 AISHELL-4\u3001AliMeeting \u7b49\u4e2d\u6587 benchmark \u4e0a\u6e2c\u8a66\uff0c\u8d85\u8d8a Gemini-2.5-Pro", 6560)] }),
          new TableRow({ children: [cell("\u5373\u6642\u6027", 2800, { bold: true }), cell("\u6279\u6b21\u8655\u7406\u70ba\u4e3b\uff08Batch\uff09\uff0c\u975e\u5373\u6642\u4e32\u6d41\u8a2d\u8a08\n\u53ef\u900f\u904e vLLM \u512a\u5316\u63a8\u8ad6\u901f\u5ea6", 6560)] }),
          new TableRow({ children: [cell("Hotwords", 2800, { bold: true }), cell("\u652f\u63f4\u81ea\u5b9a\u7fa9\u71b1\u8a5e\uff08\u4eba\u540d\u3001\u5c08\u6709\u540d\u8a5e\uff09\u63d0\u5347\u8fa8\u8b58\u7387", 6560)] }),
          new TableRow({ children: [cell("\u7ffb\u8b6f\u529f\u80fd", 2800, { bold: true }), cell("\u7121\u5167\u5efa\u7ffb\u8b6f\uff0c\u9700\u5916\u639b LLM \u8655\u7406", 6560)] }),
        ]
      }),

      heading("2.2 WhisperX\uff08\u76ee\u524d MeetingMate \u4f7f\u7528\uff09", HeadingLevel.HEADING_2),
      para("WhisperX = faster-whisper + wav2vec2 alignment + pyannote diarization\uff0c\u662f\u76ee\u524d MeetingMate \u7684\u8f49\u9304\u5f15\u64ce\u3002"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 6560],
        rows: [
          new TableRow({ children: [headerCell("\u7279\u6027", 2800), headerCell("\u8aaa\u660e", 6560)] }),
          new TableRow({ children: [cell("\u6a21\u578b\u5927\u5c0f", 2800, { bold: true }), cell("large-v3 \u7d04 3GB\uff0cCPU \u53ef\u904b\u884c\uff08int8\uff09", 6560)] }),
          new TableRow({ children: [cell("\u6838\u5fc3\u529f\u80fd", 2800, { bold: true }), cell("ASR + \u5b57\u7d1a\u6642\u9593\u6233 + Speaker Diarization\uff08\u4e09\u500b\u6a21\u578b\u4e32\u806f\uff09\nDER \u7d04 8%\uff0c\u6bd4\u55ae\u7368 pyannote \u66f4\u4f4e", 6560)] }),
          new TableRow({ children: [cell("\u8a9e\u8a00\u652f\u63f4", 2800, { bold: true }), cell("99 \u7a2e\u8a9e\u8a00\uff08Whisper \u539f\u751f\u652f\u63f4\uff09", 6560)] }),
          new TableRow({ children: [cell("\u5373\u6642\u6027", 2800, { bold: true }), cell("\u6279\u6b21\u8655\u7406\uff08Batch only\uff09\uff0c\u4e0d\u652f\u63f4\u4e32\u6d41", 6560)] }),
          new TableRow({ children: [cell("\u7ffb\u8b6f\u529f\u80fd", 2800, { bold: true }), cell("Whisper \u5167\u5efa X\u21922\u82f1\u6587\u7ffb\u8b6f\uff0c\u4f46\u4e0d\u652f\u63f4\u82f1\u2192\u4e2d\u6587", 6560)] }),
        ]
      }),

      heading("2.3 \u5176\u4ed6\u5373\u6642\u4e32\u6d41\u65b9\u6848", HeadingLevel.HEADING_2),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2200, 2200, 2200, 2760],
        rows: [
          new TableRow({ children: [headerCell("\u65b9\u6848", 2200), headerCell("\u5373\u6642\u6027", 2200), headerCell("\u4e2d\u6587\u652f\u63f4", 2200), headerCell("\u50c5\u9650\u53c3\u8003", 2760)] }),
          new TableRow({ children: [cell("NVIDIA Parakeet", 2200), cell("\u6975\u5feb (>2000x RTF)", 2200), cell("\u82f1\u6587\u70ba\u4e3b", 2200), cell("GPU \u5fc5\u9808\uff0c\u4e2d\u6587\u5f31", 2760)] }),
          new TableRow({ children: [cell("Canary Qwen 2.5B", 2200), cell("\u4e2d\u7b49", 2200), cell("\u652f\u63f4", 2200), cell("WER 5.63% \u6700\u4f4e\uff0c\u4f46\u50c5\u652f\u63f44\u8a9e\u8a00", 2760)] }),
          new TableRow({ children: [cell("Vosk / Kaldi", 2200), cell("\u5373\u6642\u4e32\u6d41", 2200), cell("\u652f\u63f4", 2200), cell("\u50b3\u7d71\u65b9\u6848\uff0c\u7cbe\u78ba\u5ea6\u8f03\u4f4e", 2760)] }),
          new TableRow({ children: [cell("Azure Speech", 2200), cell("\u5373\u6642\u4e32\u6d41", 2200), cell("\u512a\u79c0", 2200), cell("\u96f2\u7aef\u4ed8\u8cbb\u670d\u52d9\uff0c\u975e\u96e2\u7dda", 2760)] }),
        ]
      }),

      // ─── Section 3: Comparison ───
      new Paragraph({ children: [new PageBreak()] }),
      heading("\u4e09\u3001\u95dc\u9375\u6bd4\u8f03\uff1aVibeVoice-ASR vs WhisperX", HeadingLevel.HEADING_1),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2200, 3580, 3580],
        rows: [
          new TableRow({ children: [headerCell("\u6bd4\u8f03\u9805\u76ee", 2200), headerCell("VibeVoice-ASR", 3580), headerCell("WhisperX\uff08\u73fe\u7528\uff09", 3580)] }),
          new TableRow({ children: [cell("\u67b6\u69cb", 2200, { bold: true }), cell("\u55ae\u4e00\u6a21\u578b\u4e09\u5408\u4e00\n(ASR+Diarization+Timestamp)", 3580), cell("\u4e09\u6a21\u578b\u4e32\u806f\n(faster-whisper+wav2vec2+pyannote)", 3580)] }),
          new TableRow({ children: [cell("\u53c3\u6578\u91cf", 2200, { bold: true }), cell("9B\uff08\u5927\uff09", 3580), cell("~3B\uff08\u7d44\u5408\uff09", 3580)] }),
          new TableRow({ children: [cell("\u786c\u9ad4\u9700\u6c42", 2200, { bold: true }), cell("24GB+ GPU VRAM", 3580, { color: "CC0000" }), cell("CPU \u53ef\u904b\u884c (int8)\nGPU \u53ef\u52a0\u901f", 3580, { color: "006600" })] }),
          new TableRow({ children: [cell("Diarization", 2200, { bold: true }), cell("\u5167\u5efa\uff0c\u55ae\u6b21\u63a8\u8ad6", 3580, { color: "006600" }), cell("\u9700\u984d\u5916 pyannote + HF token", 3580)] }),
          new TableRow({ children: [cell("\u4e2d\u6587\u7cbe\u78ba\u5ea6", 2200, { bold: true }), cell("\u6975\u9ad8\uff08\u8d85\u8d8a Gemini-2.5-Pro\uff09", 3580, { color: "006600" }), cell("\u9ad8\uff08large-v3\uff09", 3580)] }),
          new TableRow({ children: [cell("\u5373\u6642\u4e32\u6d41", 2200, { bold: true }), cell("\u4e0d\u652f\u63f4\uff08Batch only\uff09", 3580, { color: "CC0000" }), cell("\u4e0d\u652f\u63f4\uff08Batch only\uff09", 3580, { color: "CC0000" })] }),
          new TableRow({ children: [cell("\u82f1\u2192\u4e2d\u7ffb\u8b6f", 2200, { bold: true }), cell("\u7121\u5167\u5efa", 3580), cell("\u7121\u5167\u5efa\uff08\u50c5 X\u2192\u82f1\u6587\uff09", 3580)] }),
          new TableRow({ children: [cell("\u90e8\u7f72\u96e3\u5ea6", 2200, { bold: true }), cell("\u9ad8\uff08\u9700 vLLM + GPU\uff09", 3580), cell("\u4f4e\uff08pip install\uff09", 3580, { color: "006600" })] }),
          new TableRow({ children: [cell("Hotwords", 2200, { bold: true }), cell("\u652f\u63f4", 3580, { color: "006600" }), cell("\u4e0d\u652f\u63f4", 3580)] }),
        ]
      }),

      // ─── Section 4: Architecture ───
      heading("\u56db\u3001\u5efa\u8b70\u67b6\u69cb\u8a2d\u8a08", HeadingLevel.HEADING_1),
      para("\u6839\u64da\u9700\u6c42\u5206\u6790\uff0c\u5efa\u8b70\u5c07 MeetingMate \u64f4\u5c55\u70ba\u300c\u96d9\u5f15\u64ce\u300d\u67b6\u69cb\uff1a"),

      heading("4.1 \u529f\u80fd A\uff1a\u5373\u6642\u8a9e\u97f3\u8f49\u6587\u5b57 + \u5373\u6642\u7ffb\u8b6f + \u5373\u6642\u91cd\u9ede", HeadingLevel.HEADING_2),
      para("\u7531\u65bc VibeVoice-ASR \u8207 WhisperX \u90fd\u4e0d\u652f\u63f4\u5373\u6642\u4e32\u6d41\uff0c\u5373\u6642\u529f\u80fd\u9700\u8981\u4e0d\u540c\u7684\u6280\u8853\u7d44\u5408\uff1a", { bold: true }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2200, 7160],
        rows: [
          new TableRow({ children: [headerCell("\u5c64", 2200), headerCell("\u5efa\u8b70\u65b9\u6848", 7160)] }),
          new TableRow({ children: [cell("\u5373\u6642 STT", 2200, { bold: true }), cell("\u65b9\u6848 A\uff1aAzure Speech SDK\uff08\u96f2\u7aef\uff0c\u4e2d\u82f1\u6587\u6700\u4f73\uff0c\u4ed8\u8cbb\uff09\n\u65b9\u6848 B\uff1afaster-whisper streaming mode\uff08\u96e2\u7dda\uff0c\u5c07\u97f3\u8a0a\u5207\u5272\u6210\u5c0f\u584a\u905e\u589e\u8f49\u9304\uff09\n\u65b9\u6848 C\uff1aVosk\uff08\u96e2\u7dda\u5373\u6642\uff0c\u7cbe\u78ba\u5ea6\u8f03\u4f4e\u4f46\u5ef6\u9072\u6975\u4f4e\uff09", 7160)] }),
          new TableRow({ children: [cell("\u5373\u6642\u82f1\u2192\u4e2d\u7ffb\u8b6f", 2200, { bold: true }), cell("LLM API \u5373\u6642\u7ffb\u8b6f\uff08Streaming\uff09\uff1a\n\u6bcf\u7576\u7d2f\u7a4d\u4e00\u53e5\u5b8c\u6574\u7684\u82f1\u6587\uff0c\u900f\u904e GPT-4o / Claude / Gemini API \u5373\u6642\u7ffb\u8b6f\u6210\u4e2d\u6587\uff0c\u4ee5 SSE \u63a8\u9001\u5230\u524d\u7aef", 7160)] }),
          new TableRow({ children: [cell("\u5373\u6642\u91cd\u9ede\u6458\u8981", 2200, { bold: true }), cell("LLM \u6eda\u52d5\u6458\u8981\uff1a\n\u6bcf 2\u20133 \u5206\u9418\u5c07\u7d2f\u7a4d\u7684\u8f49\u9304\u5167\u5bb9\u50b3\u7d66 LLM\uff0c\u7522\u751f\u300c\u5373\u6642\u91cd\u9ede\u300d\u986f\u793a\u5728\u5074\u6b04\n\u6703\u8b70\u7d50\u675f\u5f8c\u518d\u7528\u5b8c\u6574\u8f49\u9304\u7a3f\u7522\u751f\u6b63\u5f0f\u6458\u8981", 7160)] }),
        ]
      }),

      heading("4.2 \u529f\u80fd B\uff1a\u9304\u97f3\u6a94\u6703\u8b70\u8a18\u9304 + \u7ffb\u8b6f\uff08\u5df2\u6709\u57fa\u790e\uff09", HeadingLevel.HEADING_2),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2200, 7160],
        rows: [
          new TableRow({ children: [headerCell("\u5c64", 2200), headerCell("\u5efa\u8b70\u65b9\u6848", 7160)] }),
          new TableRow({ children: [cell("\u96e2\u7dda STT", 2200, { bold: true }), cell("\u73fe\u6709 WhisperX\uff08\u7dad\u6301\uff09\n\u53ef\u9078\u64c7\u5347\u7d1a\u70ba VibeVoice-ASR\uff08\u82e5\u6709 GPU\uff09", 7160)] }),
          new TableRow({ children: [cell("\u8aaa\u8a71\u8005\u8fa8\u8b58", 2200, { bold: true }), cell("WhisperX + pyannote\uff08\u73fe\u6709\uff09\nVibeVoice-ASR \u5167\u5efa\uff08\u66f4\u7cbe\u78ba\uff09", 7160)] }),
          new TableRow({ children: [cell("\u82f1\u2192\u4e2d\u7ffb\u8b6f", 2200, { bold: true }), cell("\u65b0\u589e\u529f\u80fd\uff1a\u8f49\u9304\u5b8c\u6210\u5f8c\uff0c\u7528 LLM \u5c07\u82f1\u6587\u8f49\u9304\u7a3f\u7ffb\u8b6f\u6210\u4e2d\u6587\n\u53ef\u4f5c\u70ba\u300c\u7ffb\u8b6f\u300d\u6309\u9215\u52a0\u5728\u6703\u8b70\u8a73\u7d30\u9801", 7160)] }),
          new TableRow({ children: [cell("\u6703\u8b70\u6458\u8981", 2200, { bold: true }), cell("\u73fe\u6709 LLM \u6458\u8981\u529f\u80fd\uff08\u7dad\u6301\uff09", 7160)] }),
        ]
      }),

      // ─── Section 5: Recommendations ───
      heading("\u4e94\u3001\u5be6\u4f5c\u512a\u5148\u7d1a\u5efa\u8b70", HeadingLevel.HEADING_1),
      para("\u6839\u64da\u6280\u8853\u8907\u96dc\u5ea6\u3001\u5be6\u7528\u6027\u548c\u6210\u672c\u8003\u91cf\uff0c\u5efa\u8b70\u4ee5\u4e0b\u5be6\u4f5c\u9806\u5e8f\uff1a"),

      para("Phase 1\uff1a\u9304\u97f3\u6a94\u7ffb\u8b6f\u529f\u80fd\uff08\u6700\u7c21\u55ae\uff0c1\u20132\u5929\uff09", { bold: true, color: "2E5B8A" }),
      bullet("\u5728\u73fe\u6709\u6703\u8b70\u8a73\u7d30\u9801\u65b0\u589e\u300c\u7ffb\u8b6f\u300d\u6309\u9215\uff0c\u8f49\u9304\u5b8c\u6210\u5f8c\u53ef\u5c07\u82f1\u6587\u8f49\u9304\u7a3f\u900f\u904e LLM \u7ffb\u8b6f\u6210\u4e2d\u6587", "recs"),
      bullet("\u4f7f\u7528\u73fe\u6709 LLM API\uff08GPT-4o / Claude / Gemini\uff09\uff0c\u7121\u9700\u65b0\u5f15\u64ce", "recs"),
      bullet("\u96e3\u5ea6\u4f4e\uff0c\u53ea\u9700\u65b0\u589e\u4e00\u500b API endpoint + \u524d\u7aef\u6309\u9215", "recs"),

      para("Phase 2\uff1a\u5373\u6642\u8a9e\u97f3\u8f49\u6587\u5b57\uff08\u4e2d\u7b49\u96e3\u5ea6\uff0c3\u20135\u5929\uff09", { bold: true, color: "2E5B8A" }),
      bullet("\u65b0\u589e\u300c\u5373\u6642\u8f49\u9304\u300d\u9801\u9762\uff0c\u900f\u904e\u700f\u89bd\u5668\u9ea5\u514b\u98a8\u64f7\u53d6\u97f3\u8a0a", "recs"),
      bullet("\u5efa\u8b70\u63a1\u7528 faster-whisper \u5207\u5757\u905e\u589e\u8f49\u9304\uff08\u6bcf 5 \u79d2\u8655\u7406\u4e00\u6b21\uff09\u2014\u2014 \u96e2\u7dda\u53ef\u7528\u3001\u514d\u8cbb", "recs"),
      bullet("\u6216\u63a1\u7528 Azure Speech SDK\uff08\u96f2\u7aef\uff09\u2014\u2014 \u4e2d\u82f1\u6587\u6df7\u5408\u6700\u4f73\uff0c\u4f46\u9700\u4ed8\u8cbb", "recs"),

      para("Phase 3\uff1a\u5373\u6642\u82f1\u2192\u4e2d\u7ffb\u8b6f + \u5373\u6642\u91cd\u9ede\uff08\u8f03\u9ad8\u96e3\u5ea6\uff0c3\u20145\u5929\uff09", { bold: true, color: "2E5B8A" }),
      bullet("\u5373\u6642\u8f49\u9304\u7684\u82f1\u6587\u5b57\u5e55\u900f\u904e LLM Streaming API \u5373\u6642\u7ffb\u8b6f\u6210\u4e2d\u6587", "recs"),
      bullet("\u6bcf 2\u20133 \u5206\u9418\u7528 LLM \u7522\u751f\u5373\u6642\u91cd\u9ede\uff0c\u986f\u793a\u5728\u5074\u6b04", "recs"),
      bullet("\u9700\u8981 WebSocket / SSE \u5be6\u73fe\u524d\u5f8c\u7aef\u5373\u6642\u901a\u8a0a", "recs"),

      para("Phase 4\uff08\u9078\u914d\uff09\uff1a\u5347\u7d1a\u70ba VibeVoice-ASR", { bold: true, color: "2E5B8A" }),
      bullet("\u82e5\u672a\u4f86\u6709 GPU \u4f3a\u670d\u5668\uff0c\u53ef\u5c07\u96e2\u7dda\u8f49\u9304\u5f15\u64ce\u5347\u7d1a\u70ba VibeVoice-ASR", "recs"),
      bullet("\u512a\u52e2\uff1a\u66f4\u9ad8\u7684\u4e2d\u6587\u7cbe\u78ba\u5ea6\u3001\u5167\u5efa diarization\u3001\u652f\u63f4 hotwords", "recs"),
      bullet("\u524d\u63d0\uff1a\u9700\u8981 24GB+ GPU VRAM\uff08\u5982 RTX 4090 \u6216\u96f2\u7aef GPU\uff09", "recs"),

      // ─── Section 6: Cost ───
      heading("\u516d\u3001\u6210\u672c\u8a55\u4f30", HeadingLevel.HEADING_1),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2500, 2200, 2200, 2460],
        rows: [
          new TableRow({ children: [headerCell("\u9805\u76ee", 2500), headerCell("\u96e2\u7dda\u65b9\u6848", 2200), headerCell("\u96f2\u7aef\u65b9\u6848", 2200), headerCell("\u8aaa\u660e", 2460)] }),
          new TableRow({ children: [cell("\u5373\u6642 STT", 2500), cell("\u514d\u8cbb\n(faster-whisper)", 2200, { color: "006600" }), cell("~$1/\u5c0f\u6642\n(Azure Speech)", 2200), cell("\u96e2\u7dda\u7cbe\u78ba\u5ea6\u7a0d\u4f4e\n\u96f2\u7aef\u4e2d\u82f1\u6587\u6df7\u5408\u6700\u4f73", 2460)] }),
          new TableRow({ children: [cell("\u5373\u6642\u7ffb\u8b6f", 2500), cell("N/A", 2200), cell("~$0.01/\u6bcf\u6b21\n(LLM API)", 2200), cell("\u6bcf\u53e5\u8abf\u7528\u4e00\u6b21 LLM", 2460)] }),
          new TableRow({ children: [cell("\u5373\u6642\u91cd\u9ede", 2500), cell("N/A", 2200), cell("~$0.02/\u6bcf\u6b21\n(LLM API)", 2200), cell("\u6bcf 2-3 \u5206\u9418\u8abf\u7528\u4e00\u6b21", 2460)] }),
          new TableRow({ children: [cell("\u9304\u97f3\u6a94\u7ffb\u8b6f", 2500), cell("~$0.03/\u6b21\n(LLM API)", 2200), cell("\u540c\u5de6", 2200), cell("\u5168\u6587\u7ffb\u8b6f\u55ae\u6b21\u8abf\u7528", 2460)] }),
          new TableRow({ children: [cell("VibeVoice-ASR", 2500), cell("\u514d\u8cbb\n(\u9700 GPU)", 2200, { color: "006600" }), cell("~$0.5/\u5c0f\u6642\n(\u96f2\u7aef GPU)", 2200), cell("\u9700 24GB+ VRAM", 2460)] }),
        ]
      }),

      // ─── Section 7: Conclusion ───
      heading("\u4e03\u3001\u7d50\u8ad6", HeadingLevel.HEADING_1),
      para("VibeVoice-ASR \u662f\u76ee\u524d\u6700\u5f37\u7684\u958b\u6e90\u8a9e\u97f3\u8fa8\u8b58\u6a21\u578b\uff0c\u4f46\u5b83\u4e26\u975e\u5373\u6642\u4e32\u6d41\u5f15\u64ce\uff0c\u800c\u662f\u6279\u6b21\u8655\u7406\u6a21\u578b\uff0c\u4e14\u786c\u9ad4\u9700\u6c42\u9ad8\u3002\u5b83\u6c92\u6709\u5167\u5efa\u7ffb\u8b6f\u529f\u80fd\u3002"),
      para("\u5c0d\u65bc MeetingMate \u7684\u5373\u6642\u9700\u6c42\uff0c\u6700\u52d9\u5be6\u7684\u505a\u6cd5\u662f\uff1a", { bold: true }),
      bullet("\u96e2\u7dda\u8f49\u9304\uff1a\u7e7c\u7e8c\u4f7f\u7528 WhisperX\uff08\u5df2\u6709\uff09\uff0cCPU \u53ef\u904b\u884c\uff0c\u5920\u7528", "bullets"),
      bullet("\u5373\u6642\u8f49\u9304\uff1a\u7528 faster-whisper \u5207\u584a\u905e\u589e\u6216 Azure Speech SDK", "bullets"),
      bullet("\u82f1\u2192\u4e2d\u7ffb\u8b6f\uff1a\u7d71\u4e00\u7528 LLM API \u8655\u7406\uff08\u5373\u6642\u548c\u96e2\u7dda\u90fd\u9069\u7528\uff09", "bullets"),
      bullet("\u5373\u6642\u91cd\u9ede\uff1aLLM \u6eda\u52d5\u6458\u8981\uff08\u6bcf 2\u20133 \u5206\u9418\u66f4\u65b0\u4e00\u6b21\uff09", "bullets"),
      bullet("VibeVoice-ASR\uff1a\u7559\u5f85\u672a\u4f86\u6709 GPU \u6642\u518d\u5347\u7d1a\uff0c\u4f5c\u70ba Phase 4 \u9078\u914d", "bullets"),

      para(""),
      para("\u5efa\u8b70\u5f9e Phase 1\uff08\u9304\u97f3\u6a94\u7ffb\u8b6f\uff09\u958b\u59cb\u5be6\u4f5c\uff0c\u9019\u662f\u6700\u5feb\u80fd\u770b\u5230\u6548\u679c\u7684\u529f\u80fd\uff0c\u4e14\u6280\u8853\u96e3\u5ea6\u6700\u4f4e\u3002", { bold: true, color: "2E5B8A" }),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/confident-sweet-lamport/mnt/MeetingMate/MeetingMate_技術評估報告.docx", buffer);
  console.log("Document created successfully");
});
