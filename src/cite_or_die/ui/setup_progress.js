export function updateSetupProgressDisclosure() {
  const strip = document.getElementById("setup-strip");
  if (!strip) return;

  const cards = [...document.querySelectorAll(".setup-step-card")];
  const complete = setupComplete(cards);
  strip.dataset.setupComplete = String(complete);
  updateSetupHeading(complete);
  updateSetupSummary({ cards, complete });
  updateSetupExpanded(strip, complete);
}

function setupComplete(cards) {
  if (!cards.length) return false;
  return cards.every((card) => card.dataset.setupState === "ready");
}

function updateSetupHeading(complete) {
  const heading = document.getElementById("setup-heading");
  if (!heading) return;
  heading.textContent = setupHeadingText(complete);
}

function setupHeadingText(complete) {
  if (complete) return "Deal workflow ready";
  return "Deal workflow";
}

function updateSetupSummary(progress) {
  const summary = document.getElementById("setup-summary");
  if (!summary) return;
  summary.textContent = setupSummaryText(progress);
}

function setupSummaryText({ cards, complete }) {
  if (complete) return "Provider, sources, and cited outputs are ready.";
  return incompleteSetupSummary(cards);
}

function incompleteSetupSummary(cards) {
  const [provider, dealRoom] = cards;
  if (setupCardState(provider) !== "ready") {
    return "Confirm the model provider, add deal files, then run the accelerator.";
  }
  if (setupCardState(dealRoom) !== "ready") {
    return "Provider ready. Add deal files, then run the accelerator.";
  }
  return "Provider and sources ready. Run the accelerator.";
}

function setupCardState(card) {
  if (!card) return "";
  return card.dataset.setupState;
}

function updateSetupExpanded(strip, complete) {
  if (complete) {
    strip.removeAttribute("open");
  } else {
    strip.setAttribute("open", "open");
  }
}
