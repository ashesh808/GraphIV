import { Suspense } from "react";
import { Library } from "@/components/library";
import { loadLibrary } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function Home() {
  const result = await loadLibrary();
  return <Suspense fallback={<main id="main-content" className="page-status">Loading the library…</main>}><Library result={result} /></Suspense>;
}
