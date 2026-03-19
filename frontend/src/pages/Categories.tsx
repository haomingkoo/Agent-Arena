import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getCategories, type Category } from '../lib/api';
import Skeleton from '../components/Skeleton';
import CategoryBadge from '../components/CategoryBadge';

function CategoriesSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-10 text-center">
        <Skeleton className="mx-auto h-10 w-60 max-w-full" />
        <Skeleton className="mx-auto mt-3 h-5 w-96 max-w-full" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-border bg-bg-card p-5">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="mt-3 h-4 w-full" />
            <Skeleton className="mt-2 h-4 w-3/4" />
            <div className="mt-4 flex gap-4">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-20" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Categories() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getCategories()
      .then((data) => setCategories(data.categories))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <CategoriesSkeleton />;

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load categories: {error}</p>
          <p className="mt-2 text-sm text-text-muted">
            Make sure the API is running at localhost:8000
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          <span className="text-cyan-accent">Legacy Categories</span>
        </h1>
        <p className="mt-2 text-base text-text-secondary sm:text-lg">
          Prompt-artifact categories from the older skill-oriented benchmark flow.
        </p>
      </div>

      {categories.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg-card p-12 text-center">
          <p className="text-text-muted">No categories configured yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {categories.map((cat) => (
            <Link
              key={cat.slug}
              to={`/categories/${encodeURIComponent(cat.slug)}`}
              className="group rounded-lg border border-border bg-bg-card p-5 no-underline transition-colors hover:border-cyan-accent/40 hover:bg-bg-hover"
            >
              <div className="flex items-center gap-2">
                <CategoryBadge category={cat.slug} size="md" />
                {!cat.active && (
                  <span className="rounded bg-bg-secondary px-1.5 py-0.5 text-xs text-text-muted">
                    inactive
                  </span>
                )}
              </div>
              <h2 className="mt-3 text-lg font-semibold text-text-primary group-hover:text-cyan-accent transition-colors">
                {cat.display_name}
              </h2>
              <p className="mt-1 text-sm text-text-secondary line-clamp-2">
                {cat.description}
              </p>
              <div className="mt-4 flex gap-4 text-sm text-text-muted">
                <span>
                  <span className="font-mono font-medium text-text-primary">{cat.skill_count}</span> artifacts
                </span>
                <span>
                  <span className="font-mono font-medium text-text-primary">{cat.task_count}</span> tasks
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
