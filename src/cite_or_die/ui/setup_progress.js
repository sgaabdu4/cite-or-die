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
  if (complete) return "Setup complete";
  return "Next action";
}

function updateSetupSummary(progress) {
  const summary = document.getElementById("setup-summary");
  if (!summary) return;
  summary.textContent = setupSummaryText(progress);
}

function setupSummaryText({ cards, complete }) {
  if (complete) return "Setup complete. Provider, deal room, and review outputs are ready.";
  return incompleteSetupSummary(cards);
}

function incompleteSetupSummary(cards) {
  const [provider, dealRoom] = cards;
  if (setupCardState(provider) !== "ready") {
    return "Connect a model provider, load sources, then run the review.";
  }
  if (setupCardState(dealRoom) !== "ready") {
    return "Provider ready. Load a deal room, then run the review.";
  }
  return "Provider and deal room ready. Run the review.";
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
