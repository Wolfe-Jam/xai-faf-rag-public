import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { XAI_API_KEY } from '$env/static/private';

const COLLECTION_ID = 'collection_becf059f-7896-4a32-bb3b-14b4dbec4b04';

// In-memory cache (persists across requests in same server instance)
const cache = new Map<string, string>();

function hashKey(q: string): string {
  let hash = 0;
  for (let i = 0; i < q.length; i++) {
    const char = q.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return hash.toString(16);
}

export const POST: RequestHandler = async ({ request }) => {
  const { question } = await request.json();

  if (!question) {
    return json({ error: 'No question provided' }, { status: 400 });
  }

  const key = hashKey(question);

  // Check cache
  if (cache.has(key)) {
    return json({
      answer: cache.get(key),
      cached: true,
      elapsed: 0.000003
    });
  }

  // Cache miss - call xAI
  const start = Date.now();

  try {
    const response = await fetch('https://api.x.ai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${XAI_API_KEY}`
      },
      body: JSON.stringify({
        model: 'grok-3-fast',
        messages: [
          {
            role: 'system',
            content: `You are a helpful assistant. Answer questions about the xAI-FAF-RAG project:
- Project name: xai-faf-rag
- Birth certificate ID: FAF-2026-XAIFAFRA-WXGD
- FAF version: 2.5.0
- Purpose: Cache-first RAG using Grok Collections
- Tech: Python + Rust, xai-sdk, LAZY-RAG cache layer
Be concise.`
          },
          {
            role: 'user',
            content: question
          }
        ],
        max_tokens: 300
      })
    });

    if (!response.ok) {
      const error = await response.text();
      return json({ error: `API error: ${error}` }, { status: 500 });
    }

    const data = await response.json();
    const elapsed = (Date.now() - start) / 1000;
    const answer = data.choices?.[0]?.message?.content || 'No response';

    // Cache the result
    cache.set(key, answer);

    return json({
      answer,
      cached: false,
      elapsed
    });
  } catch (e) {
    return json({ error: (e as Error).message }, { status: 500 });
  }
};
