/**
 * `/reading/play` layout — mounts the v2 immersive bottom nav (ISSUE-096).
 *
 * The shell resolves to `bottom-v2` for `/reading/play` and nested
 * sub-routes. When the flag is off, the shell is a pass-through and the
 * page's existing chrome remains the only nav surface.
 */
import { RouteShell } from '@/components/nav/RouteShell';

export default function PlayLayout({ children }: { children: React.ReactNode }) {
  return <RouteShell>{children}</RouteShell>;
}
