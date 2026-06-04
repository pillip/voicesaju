/**
 * `/me/*` layout — mounts the v2 hanja tab bar via `<RouteShell>` (ISSUE-096).
 *
 * `RouteShell` resolves `usePathname()` and renders the hanja-tab variant for
 * any route starting with `/me`. When `NEXT_PUBLIC_NAV_V2` is unset (the
 * production default) the shell short-circuits and renders children alone,
 * so the existing `TopAppBar`/`BottomTabBar` chrome on the pages remains
 * the only nav — i.e. the rollback path is "do nothing".
 *
 * The layout itself is a plain Server Component; the shell is the only
 * client island. This keeps the per-route SSR cost minimal.
 */
import { RouteShell } from '@/components/nav/RouteShell';

export default function MeLayout({ children }: { children: React.ReactNode }) {
  return <RouteShell>{children}</RouteShell>;
}
