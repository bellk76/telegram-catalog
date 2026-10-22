import type { Metadata } from "next";
import Script from "next/script";

import { TelegramBootstrap } from "@/components/TelegramBootstrap";

import "./globals.css";

export const metadata: Metadata = {
  title: "Каталог",
  description: "Каталог товаров Telegram Mini App",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body>
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="afterInteractive"
        />
        <TelegramBootstrap />
        {children}
      </body>
    </html>
  );
}
