export type Product = {
  id: number;
  title: string;
  image_url: string;
  created_at: string;
};

export type ProductList = {
  items: Product[];
  total: number;
};

export const PAGE_SIZE = 100;

const API_BASE = (
  process.env.API_INTERNAL_URL?.trim() || "http://localhost:8000"
).replace(/\/+$/, "");

function isProduct(value: unknown): value is Product {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const product = value as Record<string, unknown>;
  return (
    typeof product.id === "number" &&
    typeof product.title === "string" &&
    typeof product.image_url === "string" &&
    typeof product.created_at === "string"
  );
}

function isProductList(value: unknown): value is ProductList {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const list = value as Record<string, unknown>;
  return (
    Array.isArray(list.items) &&
    list.items.every(isProduct) &&
    typeof list.total === "number"
  );
}

export async function getProducts(offset = 0): Promise<ProductList> {
  const response = await fetch(
    `${API_BASE}/api/products?limit=${PAGE_SIZE}&offset=${offset}`,
    {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    },
  );

  if (!response.ok) {
    throw new Error(`API responded with ${response.status}`);
  }

  const payload: unknown = await response.json();
  if (!isProductList(payload)) {
    throw new Error("Unexpected /api/products response shape");
  }

  return payload;
}
