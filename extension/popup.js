document.addEventListener("DOMContentLoaded", async () => {
  const statusBadge = document.getElementById("status-badge");
  const statusText = document.getElementById("status-text");
  const countText = document.getElementById("cookie-count");
  const btnDownload = document.getElementById("btn-download");
  const btnCopy = document.getElementById("btn-copy");
  const toast = document.getElementById("toast");

  let netscapeText = "";
  let cookieCount = 0;

  function showToast(msg) {
    toast.textContent = msg;
    toast.style.display = "block";
    setTimeout(() => {
      toast.style.display = "none";
    }, 2000);
  }

  function formatNetscape(cookies) {
    const lines = [
      "# Netscape HTTP Cookie File",
      "# https://curl.se/docs/http-cookies.html",
      "# Exported by AyTube Cookie Exporter",
      "# This file can be used directly with AyTube, yt-dlp, and curl.",
      "",
    ];

    for (const c of cookies) {
      const domain = c.domain.startsWith(".") ? c.domain : "." + c.domain;
      const includeSubdomains = domain.startsWith(".") ? "TRUE" : "FALSE";
      const path = c.path || "/";
      const secure = c.secure ? "TRUE" : "FALSE";
      const expiry = Math.round(c.expirationDate || (Date.now() / 1000 + 86400 * 365));
      const name = c.name;
      const value = c.value || "";

      lines.push(`${domain}\t${includeSubdomains}\t${path}\t${secure}\t${expiry}\t${name}\t${value}`);
    }

    return lines.join("\n") + "\n";
  }

  try {
    const cookies = await chrome.cookies.getAll({ domain: "youtube.com" });
    cookieCount = cookies.length;

    if (cookieCount === 0) {
      statusBadge.classList.add("error");
      statusText.textContent = "No cookies found";
      countText.textContent = "Open & log in to youtube.com first";
      btnDownload.disabled = true;
      btnCopy.disabled = true;
      return;
    }

    const hasAuth = cookies.some((c) => c.name === "LOGIN_INFO" || c.name === "SID" || c.name === "SSID");
    if (hasAuth) {
      statusText.textContent = "Logged In";
    } else {
      statusText.textContent = "Active";
    }

    countText.textContent = `Found ${cookieCount} YouTube cookies`;
    netscapeText = formatNetscape(cookies);
  } catch (err) {
    statusBadge.classList.add("error");
    statusText.textContent = "Error";
    countText.textContent = err.message || "Failed to read cookies";
    btnDownload.disabled = true;
    btnCopy.disabled = true;
    return;
  }

  // 1. Download cookies.txt
  btnDownload.addEventListener("click", () => {
    if (!netscapeText) return;
    const blob = new Blob([netscapeText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    if (chrome.downloads && chrome.downloads.download) {
      chrome.downloads.download({
        url: url,
        filename: "cookies.txt",
        saveAs: true,
      });
    } else {
      const a = document.createElement("a");
      a.href = url;
      a.download = "cookies.txt";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
    showToast("✓ cookies.txt exported!");
  });

  // 2. Copy to clipboard
  btnCopy.addEventListener("click", async () => {
    if (!netscapeText) return;
    try {
      await navigator.clipboard.writeText(netscapeText);
      showToast("✓ Copied to clipboard!");
    } catch {
      showToast("Failed to copy");
    }
  });
});
