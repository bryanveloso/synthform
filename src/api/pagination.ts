// Shape of a Ninja `@paginate` response (LimitOffsetPagination default).
// Backend list endpoints return { items, count }; the fetch helpers below
// unwrap to `items` so callers keep receiving plain arrays.
export interface Paginated<T> {
  items: T[]
  count: number
}
