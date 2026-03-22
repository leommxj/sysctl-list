function initInfoModal(): void {
  const dialog = document.querySelector<HTMLDialogElement>("#infoModal");
  const openButtons = document.querySelectorAll<HTMLButtonElement>("[data-info-open]");
  const closeButton = document.querySelector<HTMLButtonElement>("[data-info-close]");

  if (!dialog || !openButtons.length) {
    return;
  }

  const open = (): void => {
    if (dialog.open) {
      return;
    }
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
      return;
    }
    dialog.setAttribute("open", "");
  };

  const close = (): void => {
    if (!dialog.open) {
      dialog.removeAttribute("open");
      return;
    }
    if (typeof dialog.close === "function") {
      dialog.close();
      return;
    }
    dialog.removeAttribute("open");
  };

  openButtons.forEach((button) => {
    button.addEventListener("click", open);
  });

  closeButton?.addEventListener("click", close);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      close();
    }
  });
}

initInfoModal();
