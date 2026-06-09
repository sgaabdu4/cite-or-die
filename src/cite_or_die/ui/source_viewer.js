function textLineOffsets(text) {
  const offsets = [0];
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] === "\n") offsets.push(index + 1);
  }
  return offsets;
}

function lineForOffset(offsets, offset) {
  let low = 0;
  let high = offsets.length - 1;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (offsets[mid] <= offset) {
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return high + 1;
}

function normalizedTextMap(text) {
  let normalized = "";
  const map = [];
  let inWhitespace = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (/\s/.test(char)) {
      if (!inWhitespace) {
        normalized += " ";
        map.push(index);
        inWhitespace = true;
      }
    } else {
      normalized += char;
      map.push(index);
      inWhitespace = false;
    }
  }
  return { normalized, map };
}

export function locateTextQuote(text, quote) {
  const cleanQuote = quote.trim();
  if (!cleanQuote) return null;
  let start = text.indexOf(cleanQuote);
  let end = start + cleanQuote.length;
  if (start === -1) {
    const normalizedSource = normalizedTextMap(text);
    const normalizedQuote = normalizedTextMap(cleanQuote).normalized;
    const normalizedStart = normalizedSource.normalized.indexOf(normalizedQuote);
    if (normalizedStart === -1) return null;
    start = normalizedSource.map[normalizedStart] || 0;
    const normalizedEnd = normalizedStart + normalizedQuote.length - 1;
    end = (normalizedSource.map[normalizedEnd] || start) + 1;
  }
  const offsets = textLineOffsets(text);
  return {
    start,
    end,
    lineStart: lineForOffset(offsets, start),
    lineEnd: lineForOffset(offsets, Math.max(end - 1, start)),
  };
}

export function locateQuoteSegments(parts, quote) {
  const segments = [];
  let text = "";
  for (const part of parts) {
    const value = part || "";
    if (value && text) text += " ";
    const start = text.length;
    text += value;
    segments.push({ start, end: text.length });
  }
  const match = locateTextQuote(text, quote);
  if (!match) return { text, match: null, segmentIndexes: [], segmentRanges: [] };
  const segmentRanges = segments
    .map((segment, index) => ({ segment, index }))
    .filter(({ segment }) => segment.start < match.end && segment.end > match.start)
    .map(({ segment, index }) => ({
      index,
      start: Math.max(match.start, segment.start) - segment.start,
      end: Math.min(match.end, segment.end) - segment.start,
    }));
  const segmentIndexes = segmentRanges.map(({ index }) => index);
  return { text, match, segmentIndexes, segmentRanges };
}

function sourceLineRange(lineCount, match) {
  if (!match) {
    return { start: 1, end: Math.min(lineCount, 120) };
  }
  return {
    start: Math.max(1, match.lineStart - 2),
    end: Math.min(lineCount, match.lineEnd + 2),
  };
}

export function renderSourceExcerpt(text, quote) {
  const lines = text.split(/\r?\n/);
  const match = locateTextQuote(text, quote);
  const range = sourceLineRange(lines.length, match);
  const figure = document.createElement("figure");
  figure.className = "source-excerpt";
  const caption = document.createElement("figcaption");
  caption.className = "source-excerpt-title";
  if (match) {
    const label =
      match.lineStart === match.lineEnd
        ? `Cited line ${match.lineStart}`
        : `Cited lines ${match.lineStart}-${match.lineEnd}`;
    caption.textContent = label;
  } else if (quote) {
    caption.textContent = "Quote not found in source text";
  } else {
    caption.textContent = "Source preview";
  }
  const rows = document.createElement("div");
  rows.className = "source-lines";
  for (let lineNumber = range.start; lineNumber <= range.end; lineNumber += 1) {
    const row = document.createElement("div");
    row.className = "source-line";
    if (match && lineNumber >= match.lineStart && lineNumber <= match.lineEnd) {
      row.classList.add("is-cited");
    }
    const number = document.createElement("span");
    number.className = "source-line-number";
    number.textContent = String(lineNumber);
    const body = document.createElement("span");
    body.className = "source-line-text";
    body.textContent = lines[lineNumber - 1] || " ";
    row.append(number, body);
    rows.append(row);
  }
  figure.append(caption, rows);
  if (!match && quote) {
    const quoteBlock = document.createElement("blockquote");
    quoteBlock.className = "source-missing-quote";
    quoteBlock.textContent = quote;
    figure.append(quoteBlock);
  }
  return { figure, match };
}
