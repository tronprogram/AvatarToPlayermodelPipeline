(function () {
  function csrfToken() {
    const input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : "";
  }

  async function pickFolder() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.pick_folder) {
      try {
        const picked = await window.pywebview.api.pick_folder();
        if (picked) return picked;
      } catch (err) {
        console.warn(err);
      }
    }
    return window.prompt("Folder path") || "";
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-pick-folder]");
    if (!button) return;
    event.preventDefault();
    const path = await pickFolder();
    if (!path) return;
    const form = document.createElement("form");
    form.method = "post";
    form.action = button.getAttribute("data-action") || "/settings/point";
    const fields = {
      csrf_token: csrfToken(),
      field: button.getAttribute("data-field") || "",
      path: path,
    };
    for (const [name, value] of Object.entries(fields)) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      form.appendChild(input);
    }
    document.body.appendChild(form);
    form.submit();
  });

  document.addEventListener("change", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
    const drop = input.closest(".drop");
    if (!drop) return;
    const label = drop.querySelector("span:last-child");
    if (input.files && input.files[0] && label) {
      label.textContent = input.files[0].name;
      drop.classList.add("is-set");
    }
  });
})();
