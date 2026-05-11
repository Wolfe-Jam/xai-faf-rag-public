<script lang="ts">
  let question = '';
  let result = '';
  let cacheStatus = '';
  let elapsed = '';
  let loading = false;
  let history: { q: string; a: string; cache: boolean; time: number }[] = [];

  const presetQuestions = [
    'What is the project name?',
    'What is the birth certificate ID?',
    'What is the FAF version?',
    'What are the main project goals?',
    'What are the core reasoning skills?'
  ];

  async function ask() {
    if (!question.trim()) return;
    loading = true;
    result = '';
    cacheStatus = '';
    elapsed = '';

    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });
      const data = await res.json();

      result = data.answer;
      cacheStatus = data.cached ? 'CACHE HIT' : 'API CALL';
      elapsed = data.cached ? '0.003ms' : `${data.elapsed.toFixed(1)}s`;

      history = [
        { q: question, a: data.answer, cache: data.cached, time: data.elapsed },
        ...history.slice(0, 9)
      ];
    } catch (e) {
      result = 'Error: ' + (e as Error).message;
    }
    loading = false;
  }

  function setQuestion(q: string) {
    question = q;
  }
</script>

<svelte:head>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;700&display=swap');
  </style>
</svelte:head>

<main>
  <h1>🍊 xAI-FAF-RAG Demo</h1>
  <p class="subtitle">Cache-first RAG on Grok Collections</p>

  <div class="input-section">
    <input
      type="text"
      bind:value={question}
      placeholder="Ask about the project..."
      on:keydown={(e) => e.key === 'Enter' && ask()}
    />
    <button on:click={ask} disabled={loading}>
      {loading ? 'Asking...' : 'Ask Grok'}
    </button>
  </div>

  <div class="presets">
    {#each presetQuestions as q}
      <button class="preset" on:click={() => setQuestion(q)}>{q}</button>
    {/each}
  </div>

  {#if result}
    <div class="result">
      <div class="status">
        <span class="badge {cacheStatus === 'CACHE HIT' ? 'hit' : 'miss'}">
          {cacheStatus}
        </span>
        <span class="time">{elapsed}</span>
      </div>
      <div class="answer">{result}</div>
    </div>
  {/if}

  {#if history.length > 0}
    <div class="history">
      <h3>History</h3>
      {#each history as h}
        <div class="history-item">
          <span class="badge small {h.cache ? 'hit' : 'miss'}">
            {h.cache ? 'HIT' : 'API'}
          </span>
          <strong>{h.q}</strong>
        </div>
      {/each}
    </div>
  {/if}

  <footer>
    <p>Collection: <code>collection_becf059f-7896-4a32-bb3b-14b4dbec4b04</code></p>
    <p>For Grok. For the rockets. For Mars.</p>
  </footer>
</main>

<style>
  :global(body) {
    font-family: 'Roboto Mono', monospace;
    background: #000;
    color: #fff;
    margin: 0;
    padding: 20px;
  }

  main {
    max-width: 800px;
    margin: 0 auto;
  }

  h1 {
    color: #FF6B00;
    margin-bottom: 0;
  }

  .subtitle {
    color: #00D4D4;
    margin-top: 5px;
  }

  .input-section {
    display: flex;
    gap: 10px;
    margin: 30px 0;
  }

  input {
    flex: 1;
    padding: 15px;
    font-size: 16px;
    font-family: inherit;
    background: #111;
    border: 2px solid #333;
    color: #fff;
    border-radius: 8px;
  }

  input:focus {
    outline: none;
    border-color: #FF6B00;
  }

  button {
    padding: 15px 30px;
    font-size: 16px;
    font-family: inherit;
    background: #FF6B00;
    color: #000;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: bold;
  }

  button:hover {
    background: #FF9500;
  }

  button:disabled {
    background: #444;
    cursor: not-allowed;
  }

  .presets {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 30px;
  }

  .preset {
    padding: 8px 12px;
    font-size: 12px;
    background: #222;
    color: #888;
  }

  .preset:hover {
    background: #333;
    color: #fff;
  }

  .result {
    background: #111;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 30px;
  }

  .status {
    display: flex;
    gap: 15px;
    margin-bottom: 15px;
  }

  .badge {
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 14px;
    font-weight: bold;
  }

  .badge.hit {
    background: #0a2e0a;
    color: #00ff00;
  }

  .badge.miss {
    background: #2e1a0a;
    color: #FF6B00;
  }

  .badge.small {
    padding: 2px 8px;
    font-size: 10px;
  }

  .time {
    color: #00D4D4;
    font-size: 14px;
  }

  .answer {
    line-height: 1.6;
    white-space: pre-wrap;
  }

  .history {
    border-top: 1px solid #333;
    padding-top: 20px;
  }

  .history h3 {
    color: #666;
    font-size: 14px;
  }

  .history-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    color: #888;
    font-size: 13px;
  }

  footer {
    margin-top: 50px;
    text-align: center;
    color: #444;
    font-size: 12px;
  }

  footer code {
    color: #666;
  }
</style>
