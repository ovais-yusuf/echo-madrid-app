export async function GET(_request: Request, {params}: {params: Promise<{id: string}>}) {
  const {id} = await params;
  if (!/^\d+$/.test(id)) return new Response("Invalid fixture", {status: 400});
  const base = (process.env.API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  const response = await fetch(`${base}/calendar/${id}.ics`, {cache: "no-store", signal: AbortSignal.timeout(10000)});
  if (!response.ok) return new Response("Calendar unavailable", {status: response.status});
  return new Response(await response.text(), {headers: {"Content-Type": "text/calendar", "Content-Disposition": `attachment; filename="echo-madrid-${id}.ics"`}});
}
