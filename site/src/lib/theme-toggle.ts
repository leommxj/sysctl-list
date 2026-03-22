const themeStorageKey = "sysctl-explorer.theme";

type Theme = "dark" | "light";

function isTheme(value: string | null): value is Theme {
  return value === "dark" || value === "light";
}

function getTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function syncButtons(theme: Theme): void {
  const buttons = document.querySelectorAll<HTMLButtonElement>("[data-theme-toggle]");
  buttons.forEach((button) => {
    button.textContent = theme === "dark" ? "Dark" : "Light";
    button.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} theme`);
    button.setAttribute("aria-pressed", String(theme === "dark"));
  });
}

function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  syncButtons(theme);
  try {
    window.localStorage.setItem(themeStorageKey, theme);
  } catch {
    return;
  }
}

function initThemeToggle(): void {
  const buttons = document.querySelectorAll<HTMLButtonElement>("[data-theme-toggle]");
  if (!buttons.length) {
    return;
  }

  const storedTheme = window.localStorage.getItem(themeStorageKey);
  if (isTheme(storedTheme)) {
    document.documentElement.dataset.theme = storedTheme;
  }

  syncButtons(getTheme());

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      applyTheme(getTheme() === "dark" ? "light" : "dark");
    });
  });
}

initThemeToggle();
