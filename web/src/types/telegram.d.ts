export {};

type TelegramThemeParams = {
  bg_color?: string;
  text_color?: string;
  secondary_bg_color?: string;
  hint_color?: string;
  section_separator_color?: string;
  button_color?: string;
  button_text_color?: string;
};

type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  colorScheme?: "light" | "dark";
  themeParams?: TelegramThemeParams;
  onEvent?: (event: "themeChanged", handler: () => void) => void;
  offEvent?: (event: "themeChanged", handler: () => void) => void;
};

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}
