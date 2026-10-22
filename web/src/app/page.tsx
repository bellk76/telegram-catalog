import Link from "next/link";

import { RefreshButton } from "@/components/RefreshButton";
import { PAGE_SIZE, getProducts, type ProductList } from "@/lib/api";

export const dynamic = "force-dynamic";

const MAX_PAGE = 10_001;

type CatalogPageProps = {
  searchParams: Promise<{ page?: string | string[] }>;
};

function parsePage(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw || !/^\d+$/.test(raw)) {
    return 1;
  }
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed < 1) {
    return 1;
  }
  return Math.min(parsed, MAX_PAGE);
}

function CatalogUnavailable() {
  return (
    <main className="container">
      <header className="header">
        <p className="eyebrow">Telegram Mini App</p>
        <h1>Каталог</h1>
      </header>
      <section className="empty">
        <h2>Не удалось загрузить каталог</h2>
        <p>Сервис временно недоступен. Попробуйте обновить страницу.</p>
        <RefreshButton />
      </section>
    </main>
  );
}

export default async function CatalogPage({ searchParams }: CatalogPageProps) {
  const page = parsePage((await searchParams).page);
  let products: ProductList;

  try {
    products = await getProducts((page - 1) * PAGE_SIZE);
  } catch (error) {
    console.error("catalog fetch failed", error);
    return <CatalogUnavailable />;
  }

  const hasPrevious = page > 1;
  const hasNext = page * PAGE_SIZE < products.total;
  const catalogIsEmpty = products.total === 0;

  return (
    <main className="container">
      <header className="header">
        <p className="eyebrow">Telegram Mini App</p>
        <h1>Каталог</h1>
        <p className="hint">
          {products.total === 0
            ? "В каталоге пока нет товаров"
            : `Страница ${page} · товаров: ${products.total}`}
        </p>
      </header>

      {products.items.length === 0 ? (
        <section className="empty">
          <h2>{catalogIsEmpty ? "Каталог пуст" : "Страница пуста"}</h2>
          <p>
            {catalogIsEmpty
              ? "Добавьте первый товар через Telegram-бота."
              : "На этой странице товаров нет. Вернитесь назад."}
          </p>
        </section>
      ) : (
        <ul className="grid">
          {products.items.map((product) => (
            <li className="card" key={product.id}>
              <img
                src={`/api/products/${product.id}/image`}
                alt={product.title}
                loading="lazy"
              />
              <div className="card-body">
                <h2>{product.title}</h2>
                <span className="id">#{product.id}</span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {(hasPrevious || hasNext) && (
        <nav className="pagination" aria-label="Страницы каталога">
          {hasPrevious && <Link href={`/?page=${page - 1}`}>Назад</Link>}
          {hasNext && <Link href={`/?page=${page + 1}`}>Вперёд</Link>}
        </nav>
      )}
    </main>
  );
}
