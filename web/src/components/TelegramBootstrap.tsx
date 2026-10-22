"use client";

import { useEffect } from "react";

function applyTheme() {
  const webApp = window.Telegram?.WebApp;
  if (!webApp) {
    return;
  }

  const theme = webApp.themeParams ?? {};
  const root = document.documentElement;

  if (theme.bg_color) root.style.setProperty("--tg-bg", theme.bg_color);
  if (theme.text_color) root.style.setProperty("--tg-text", theme.text_color);
  if (theme.secondary_bg_color) {
    root.style.setProperty("--tg-surface", theme.secondary_bg_color);
  }
  if (theme.hint_color) root.style.setProperty("--tg-hint", theme.hint_color);
  if (theme.section_separator_color) {
    root.style.setProperty("--tg-border", theme.section_separator_color);
  }
  if (theme.button_color) root.style.setProperty("--tg-button", theme.button_color);
  if (theme.button_text_color) {
    root.style.setProperty("--tg-button-text", theme.button_text_color);
  }

  root.style.colorScheme = webApp.colorScheme === "dark" ? "dark" : "light";
}

export function TelegramBootstrap() {
  useEffect(() => {
    let initialized = false;

    const init = () => {
      const webApp = window.Telegram?.WebApp;
      if (!webApp) {
        return false;
      }

      applyTheme();
      webApp.ready();
      webApp.expand();
      webApp.onEvent?.("themeChanged", applyTheme);
      initialized = true;
      return true;
    };

    if (init()) {
      return () => {
        window.Telegram?.WebApp?.offEvent?.("themeChanged", applyTheme);
      };
    }

    const interval = window.setInterval(() => {
      if (init()) {
        window.clearInterval(interval);
        window.clearTimeout(timeout);
      }
    }, 100);
    const timeout = window.setTimeout(() => window.clearInterval(interval), 10_000);

    return () => {
      window.clearInterval(interval);
      window.clearTimeout(timeout);
      if (initialized) {
        window.Telegram?.WebApp?.offEvent?.("themeChanged", applyTheme);
      }
    };
  }, []);

  return null;
}
