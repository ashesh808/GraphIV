import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ReportWorkspace } from "@/components/report-workspace";
import { ConnectionNote } from "@/components/connection-note";
import { loadRun } from "@/lib/data";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Research report" };

export default async function ReportPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const result = await loadRun(slug);
  if (result.status === "not-found") notFound();
  if (!result.run) return <main id="main-content" className="page-status"><h1>This report couldn’t be loaded</h1><ConnectionNote status="error" message={result.message} /><Link className="text-link" href="/">Back to the library</Link></main>;
  return <ReportWorkspace run={result.run} source={result.source} />;
}
