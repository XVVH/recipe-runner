// recipe.js — [[ingredient]] highlight in instruction steps
(function () {
  "use strict";

  // Walk all .steps li p elements and convert [[...]] to .ing-ref spans
  document.querySelectorAll(".steps li p").forEach(p => {
    const text = p.textContent;
    if (!text.includes("[[")) return;
    p.innerHTML = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/\[\[([^\]]+)\]\]/g, '<span class="ing-ref">$1</span>');
  });
})();
