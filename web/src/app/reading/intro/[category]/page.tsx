/**
 * Server-component shell for `/reading/intro/[category]` (ISSUE-032).
 *
 * Awaits the Next 15 dynamic-params Promise here so the client component
 * can stay on React 18.3 (no `use()` API). The actual UI + audio
 * lifecycle lives in `IntroClient.tsx`.
 */
import IntroClient from "./IntroClient";

interface IntroRouteParams {
  category: string;
}

export default async function IntroRoutePage({
  params,
}: {
  params: Promise<IntroRouteParams>;
}) {
  const { category } = await params;
  return <IntroClient category={category} />;
}
