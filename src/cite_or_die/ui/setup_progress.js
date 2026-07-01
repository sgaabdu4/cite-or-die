export function updateSetupProgressDisclosure() {
  const strip = document.getElementById("setup-strip");
  if (!strip) return;

  const cards = [...document.querySelectorAll(".setup-step-card")];
  const complete = cards.length > 0 && cards.every((card) => card.dataset.setupState === "ready");
  strip.dataset.setupComplete = String(complete);

  const heading = document.getElementById("setup-heading");
  if (heading) heading.textContent = complete ? "Setup complete" : "Next action";

  const summary = document.getElementById("setup-summary");
  if (complete && summary) {
    summary.textContent = "Setup complete. Provider, deal room, and review outputs are ready.";
  } else if (summary) {
    const [provider, dealRoom] = cards;
    if (provider?.dataset.setupState !== "ready") {
      summary.textContent = "Connect a model provider, load sources, then run the review.";
    } else if (dealRoom?.dataset.setupState !== "ready") {
      summary.textContent = "Provider ready. Load a deal room, then run the review.";
    } else {
      summary.textContent = "Provider and deal room ready. Run the review.";
    }
  }

  if (complete) {
    strip.removeAttribute("open");
  } else {
    strip.setAttribute("open", "open");
  }
}
