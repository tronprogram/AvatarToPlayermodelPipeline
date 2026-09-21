(function () {
  let picking = false;

  function desktopApiReady() {
    return !!(window.pywebview && window.pywebview.api && window.pywebview.api.pick_folder);
  }

  function desktopFileApiReady() {
    return !!(window.pywebview && window.pywebview.api && window.pywebview.api.pick_file);
  }

  function waitForDesktopApi(timeoutMs) {
    if (desktopApiReady()) return Promise.resolve(true);
    if (!window.pywebview) return Promise.resolve(false);
    return new Promise((resolve) => {
      const finish = (ok) => {
        window.removeEventListener("pywebviewready", onReady);
        resolve(ok);
      };
      const onReady = () => finish(desktopApiReady());
      window.addEventListener("pywebviewready", onReady);
      setTimeout(() => finish(desktopApiReady()), timeoutMs);
    });
  }

  async function pickFileFromServer() {
    try {
      const res = await fetch("/pick-file", {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) return "";
      const data = await res.json();
      return (data && data.path) || "";
    } catch (err) {
      console.warn(err);
      return "";
    }
  }

  async function pickModelFile() {
    if (window.pywebview) {
      await waitForDesktopApi(2000);
      if (desktopFileApiReady()) {
        try {
          const path = await window.pywebview.api.pick_file();
          if (path) return path;
        } catch (err) {
          console.warn(err);
        }
      }
    }
    return pickFileFromServer();
  }

  async function pickFolderFromServer() {
    try {
      const res = await fetch("/pick-folder", {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) return "";
      const data = await res.json();
      return (data && data.path) || "";
    } catch (err) {
      console.warn(err);
      return "";
    }
  }

  async function pickFolder() {
    if (window.pywebview) {
      await waitForDesktopApi(2000);
      if (desktopApiReady()) {
        try {
          const path = await window.pywebview.api.pick_folder();
          if (path) return path;
        } catch (err) {
          console.warn(err);
        }
      }
    }
    return pickFolderFromServer();
  }

  document.addEventListener("click", async (event) => {
    const drop = event.target.closest(".drop");
    const fileInput = drop && drop.querySelector('input[type="file"][name="avatar"]');
    if (fileInput && window.pywebview) {
      event.preventDefault();
      if (picking) return;
      picking = true;
      try {
        const path = await pickModelFile();
        if (!path) return;
        const form = fileInput.form;
        const hidden = form && form.querySelector('input[name="path"]');
        if (hidden) hidden.value = path;
        const label = drop.querySelector("span:last-child");
        const slash = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
        if (label) label.textContent = slash >= 0 ? path.slice(slash + 1) : path;
        drop.classList.add("is-set");
      } finally {
        picking = false;
      }
      return;
    }

    const button = event.target.closest("[data-pick-folder]");
    if (!button || picking) return;
    event.preventDefault();
    picking = true;
    try {
      const path = await pickFolder();
      if (!path) return;
      const nearby = button.closest("form") && button.closest("form").querySelector('input[name="path"]');
      if (nearby) nearby.value = path;
      const form = document.createElement("form");
      form.method = "post";
      form.action = button.getAttribute("data-action") || "/settings/point";
      const fields = {
        field: button.getAttribute("data-field") || "",
        path: path,
        next: button.getAttribute("data-next") || "/settings",
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
    } finally {
      picking = false;
    }
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
