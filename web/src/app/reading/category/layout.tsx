/**
 * `/reading/category` layout — mounts the v2 vertical nav (ISSUE-096).
 *
 * RouteShell resolves the pathname to the "vertical" variant for this
 * exact route. When the v2 flag is off, the shell renders children alone
 * (no v2 chrome lands in the DOM); the existing page UI is unchanged.
 */
import { RouteShell } from '@/components/nav/RouteShell';

export default function CategoryLayout({ children }: { children: React.ReactNode }) {
  return <RouteShell>{children}</RouteShell>;
}
