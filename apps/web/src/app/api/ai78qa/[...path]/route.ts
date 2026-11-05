import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);

async function proxy(request: NextRequest, context: { params: { path: string[] } }) {
  const upstreamBase = process.env.AI78QA_API_URL;
  const accessKey = process.env.AI78QA_API_KEY;

  if (!upstreamBase || !accessKey) {
    return Response.json(
      { detail: "AI78QA backend is not connected. Configure AI78QA_API_URL and AI78QA_API_KEY in the Vercel project environment." },
      { status: 503 },
    );
  }

  if (!ALLOWED_METHODS.has(request.method)) {
    return Response.json({ detail: "Method not supported." }, { status: 405 });
  }

  const path = (context.params.path || []).map((segment) => encodeURIComponent(segment)).join("/");
  const incoming = new URL(request.url);
  const target = new URL(`/api/v1/${path}`, upstreamBase);
  target.search = incoming.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);
  headers.set("x-api-key", accessKey);

  const body = request.method === "GET" || request.method === "HEAD"
    ? undefined
    : await request.arrayBuffer();

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
    });

    const responseHeaders = new Headers();
    for (const name of ["content-type", "content-disposition", "cache-control"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    responseHeaders.set("x-content-type-options", "nosniff");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json({ detail: "AI78QA backend is temporarily unreachable." }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
