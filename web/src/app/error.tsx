"use client";

import { useEffect } from "react";

export default function CatalogError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("catalog render failed", error);
  }, [error]);

  return (
    <main className="container">
      <header className="header">
        <p className="eyebrow">Telegram Mini App</p>
        <h1>Каталог</h1>
      </header>
      <section className="empty">
        <h2>Не удалось загрузить каталог</h2>
        <p>Сервис временно недоступен. Попробуйте обновить страницу.</p>
        <button type="button" onClick={reset}>
          Повторить
        </button>
      </section>
    </main>
  );
}
