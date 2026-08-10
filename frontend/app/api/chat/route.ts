import { createUIMessageStream, createUIMessageStreamResponse, type UIMessage } from 'ai';

const BACKEND_URL = process.env.CSV_EDITOR_BACKEND_URL ?? 'http://localhost:3000';

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json();

  const lastUserMessage = messages.at(-1);
  const instruction =
    lastUserMessage?.parts
      ?.filter((p): p is { type: 'text'; text: string } => p.type === 'text')
      .map((p) => p.text)
      .join('\n') ?? '';

  const backendRes = await fetch(`${BACKEND_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction }),
  });

  if (!backendRes.ok) {
    const detail = await backendRes.text().catch(() => '');
    return new Response(
      JSON.stringify({ error: `Backend /chat failed: ${backendRes.status} ${detail}` }),
      { status: 502, headers: { 'Content-Type': 'application/json' } },
    );
  }

  const data: { response: string; csv: string | null } = await backendRes.json();

  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      const textId = crypto.randomUUID();
      writer.write({ type: 'text-start', id: textId });
      writer.write({ type: 'text-delta', id: textId, delta: data.response });
      writer.write({ type: 'text-end', id: textId });

      if (data.csv !== null) {
        writer.write({ type: 'data-csv', data: { content: data.csv } });
      }
    },
  });

  return createUIMessageStreamResponse({ stream });
}
