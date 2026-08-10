import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.CSV_EDITOR_BACKEND_URL ?? 'http://localhost:3000';

export async function GET() {
  const res = await fetch(`${BACKEND_URL}/documents`, {
    headers: { Accept: 'application/json' },
  });
  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const res = await fetch(`${BACKEND_URL}/documents`, {
    method: 'POST',
    body: formData,
  });
  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function DELETE(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const filename = searchParams.get('filename');
  if (!filename) {
    return new Response(JSON.stringify({ error: 'filename required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  const res = await fetch(`${BACKEND_URL}/documents/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { 'Content-Type': 'application/json' },
  });
}
