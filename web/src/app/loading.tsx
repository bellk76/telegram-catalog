export default function Loading() {
  return (
    <main className="container">
      <header className="header">
        <p className="eyebrow">Telegram Mini App</p>
        <h1>Каталог</h1>
        <p className="hint">Загружаем товары…</p>
      </header>
      <ul className="grid" role="status" aria-label="Загрузка каталога" aria-busy="true">
        {Array.from({ length: 6 }, (_, index) => (
          <li className="card skeleton" key={index} aria-hidden="true">
            <div className="skeleton-image" />
            <div className="card-body">
              <div className="skeleton-line" />
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
