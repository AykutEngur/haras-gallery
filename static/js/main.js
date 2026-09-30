document.addEventListener("DOMContentLoaded", () => {
  // Mobile nav
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("open");
      toggle.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", open);
    });
  }

  // Dismiss flash messages (auto-hide success after 6s)
  document.querySelectorAll(".flash").forEach((f) => {
    f.querySelector(".flash-close")?.addEventListener("click", () => f.remove());
    if (f.classList.contains("flash-success")) setTimeout(() => f.remove(), 6000);
  });

  // Fade-in cards on scroll
  const cards = document.querySelectorAll(".card");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); }
      });
    }, { threshold: 0.1 });
    cards.forEach((c, i) => { c.classList.add("reveal"); c.style.transitionDelay = `${(i % 3) * 80}ms`; io.observe(c); });
  }

  // Lightbox on drawing detail
  const lb = document.querySelector(".lightbox");
  const lbImg = lb?.querySelector("img");
  document.querySelectorAll("[data-lightbox]").forEach((img) => {
    img.addEventListener("click", () => {
      lbImg.src = img.src; lbImg.alt = img.alt; lb.hidden = false;
      document.body.style.overflow = "hidden";
    });
  });
  const closeLb = () => { if (lb) { lb.hidden = true; document.body.style.overflow = ""; } };
  lb?.addEventListener("click", (e) => { if (e.target !== lbImg) closeLb(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeLb(); });

  // Confirm before destructive admin actions
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => { if (!confirm(form.dataset.confirm)) e.preventDefault(); });
  });

  // Image preview on upload
  document.querySelectorAll("input[type=file][data-preview]").forEach((input) => {
    const preview = document.querySelector(input.dataset.preview);
    input.addEventListener("change", () => {
      const file = input.files[0];
      if (file && preview) { preview.src = URL.createObjectURL(file); preview.hidden = false; }
    });
  });

  // Client-side check on the commission form
  const cForm = document.querySelector(".commission form");
  if (cForm) {
    cForm.addEventListener("submit", (e) => {
      let ok = true;
      cForm.querySelectorAll("[required]").forEach((el) => {
        const bad = !el.value.trim() || (el.type === "email" && !el.value.includes("@")) ||
                    (el.type === "number" && Number(el.value) <= 0);
        el.classList.toggle("invalid", bad);
        if (bad) ok = false;
      });
      if (!ok) {
        e.preventDefault();
        cForm.querySelector(".invalid")?.focus();
      }
    });
    cForm.querySelectorAll("input, textarea").forEach((el) =>
      el.addEventListener("input", () => el.classList.remove("invalid")));
  }
});
