// recipe.js — [[ingredient]] highlight; recipe-ref links come from the build
(function () {
  "use strict";

  document.querySelectorAll(".steps li p, .comments-body").forEach((el) => {
    if (el.querySelector("a.recipe-ref")) return;
    const text = el.textContent;
    if (!text.includes("[[")) return;
    el.innerHTML = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/\[\[([^\]]+)\]\]/g, '<span class="ing-ref">$1</span>');
  });
})();