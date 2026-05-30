/**
 * `/tarot/play` route entry (ISSUE-051, Screen 13).
 *
 * Thin server-component shell that mounts the
 * :component:`<TarotPlayClient>` shell from ``./PlayClient``. Splitting
 * the page lets us keep the heavy client-only state machine in its
 * own module and the route wrapper trivially testable.
 *
 * Architecture-Ref: §6.4 (daily tarot flow).
 */

import TarotPlayClient from "./PlayClient";

export default function TarotPlayPage() {
  return <TarotPlayClient />;
}
