async function getToken() {
  const body = new FormData();
  body.set("tenant_id", document.getElementById("tenant").value || "dev");
  const response = await fetch("/dev/token", { method: "POST", body });
  const json = await response.json();
  return json.access_token;
}

document.getElementById("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = await getToken();
  const file = document.getElementById("file").files[0];
  const body = new FormData();
  body.set("file", file);
  const response = await fetch("/upload", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body,
  });
  document.getElementById("upload-result").textContent = JSON.stringify(await response.json(), null, 2);
});

document.getElementById("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = await getToken();
  const question = document.getElementById("question").value;
  const response = await fetch("/chat", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });
  const json = await response.json();
  const citations = (json.citations || [])
    .map((citation) => `<span class="citation">${citation.filename}${citation.page ? ` p.${citation.page}` : ""}</span>`)
    .join("");
  document.getElementById("answer").innerHTML = `<p>${json.answer || ""}</p>${citations}`;
});
