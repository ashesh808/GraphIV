import { checkResearch } from "../../../../lib/research-server.ts";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  return checkResearch((await context.params).id);
}
