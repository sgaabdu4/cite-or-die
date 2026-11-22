export function createCitationSourceButton(filename, onOpen) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "citation-source";
  button.textContent = filename;
  button.setAttribute("aria-label", `Open source ${filename}`);
  button.addEventListener("click", onOpen);
  return button;
}

export function createDocumentRow(documentRecord, { selected, onOpen, onSelectionChange }) {
  const item = document.createElement("li");
  if (selected) item.dataset.selected = "true";
  const row = document.createElement("div");
  row.className = "document-row";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "document-button";
  button.textContent = documentRecord.filename;
  button.addEventListener("click", onOpen);
  const scopeLabel = document.createElement("label");
  scopeLabel.className = "document-scope";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = selected;
  checkbox.setAttribute("aria-label", `Use ${documentRecord.filename} for answers`);
  checkbox.addEventListener("change", () => onSelectionChange(checkbox.checked));
  const scopeText = document.createElement("span");
  scopeText.textContent = "Use";
  scopeLabel.append(checkbox, scopeText);
  row.append(button, scopeLabel);
  const meta = document.createElement("span");
  meta.textContent = documentRecord.page_count
    ? `${documentRecord.page_count} pages`
    : documentRecord.content_type;
  item.append(row, meta);
  return item;
}
