type UIMessage = {
  parts: Array<{ type: 'text'; text: string }>;
};

const BACKEND_URL = process.env.CSV_EDITOR_BACKEND_URL ?? 'http://localhost:3000';

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json();

  const lastUserMessage = messages.at(-1);
  const instruction =
    lastUserMessage?.parts
      ?.filter((p): p is { type: 'text'; text: string } => p.type === 'text')
      .map((p) => p.text)
      .join('\n') ?? '';

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000);

  let backendRes;
  try {
    backendRes = await fetch(`${BACKEND_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction }),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    return new Response(
      JSON.stringify({ error: `Backend request failed: ${err instanceof Error ? err.message : 'Unknown error'}` }),
      { status: 502, headers: { 'Content-Type': 'application/json' } },
    );
  } finally {
    clearTimeout(timeoutId);
  }

  if (!backendRes.ok) {
    const detail = await backendRes.text().catch(() => '');
    return new Response(
      JSON.stringify({ error: `Backend /chat failed: ${backendRes.status} ${detail}` }),
      { status: 502, headers: { 'Content-Type': 'application/json' } },
    );
  }

  const data: { response: string; csv: string | null } = await backendRes.json();

  const encoder = new TextEncoder();
  const readable = new ReadableStream({
    start(controller) {
      const textId = crypto.randomUUID();
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'text-start', id: textId })}\n\n`));
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'text-delta', id: textId, delta: data.response })}\n\n`));
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'text-end', id: textId })}\n\n`));

      if (data.csv !== null) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'data-csv', data: { content: data.csv } })}\n\n`));
      }

      controller.close();
    },
  });

  return new Response(readable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  });
}

export async function DELETE() {
  const res = await fetch(`${BACKEND_URL}/chat`, { method: 'DELETE' });
  if (!res.ok) {
    return new Response(
      JSON.stringify({ error: `Backend /chat DELETE failed: ${res.status}` }),
      { status: 502, headers: { 'Content-Type': 'application/json' } },
    );
  }
  return new Response(null, { status: 204 });
}
