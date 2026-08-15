<!-- faf: xai-faf-rag-public | markdown | doc | Public About Repo for FAF RAG — .faf into Grok Collections. Source private at Wolfe-Jam/xai-faf-rag. -->
<!-- faf: doc=readme | canonical=project.faf | family=FAF | private_source=Wolfe-Jam/xai-faf-rag -->

# xai-faf-rag

[![FAF](https://mcpaas.live/badge/Wolfe-Jam/xai-faf-rag-public.svg)](https://builder.faf.one)
[![IANA: vnd.faf+yaml](https://img.shields.io/badge/IANA-vnd.faf%2Byaml-00D4D4)](https://www.iana.org/assignments/media-types/application/vnd.faf+yaml)
[![DOI: Context paper](https://img.shields.io/badge/DOI-Context%20paper-FF6B35)](https://doi.org/10.5281/zenodo.18251362)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

> 📖 **Public About Repo** — the public face of [`Wolfe-Jam/xai-faf-rag`](https://github.com/Wolfe-Jam/xai-faf-rag) (source private). README, project.faf, license — no source code. Same shape as Anthropic's [`claude-code`](https://github.com/anthropics/claude-code): public face, private engine.

**Door, not product.** `.faf` into Grok Collections. Complementary to xAI's own Collections — not a second RAG brand.

Context first. Cache-first retrieval sits in front of Collections so a hit does not pay the API again. The format is IANA-registered `.faf`. The store is theirs.

**What it is**
- A door that puts project context (`.faf`) on Grok Collections
- Cache-first in front of that store
- Built for Grok. Complementary, not a fork

**What it is not**
- A public installable package (engine stays private)
- A second memory product (that's `.fafm`)
- A vector-DB competitor

**Home:** [lazyrag.one](https://lazyrag.one) · [faf.one](https://faf.one)

**Contact:** [team@faf.one](mailto:team@faf.one)

## Citation

If you use FAF context with Grok Collections, cite the format paper:

> Wolfe, J. (2026). *Format-Driven AI Context Architecture: The .faf Standard for Persistent Project Understanding*. Zenodo. https://doi.org/10.5281/zenodo.18251362

Companion: [Memory](https://doi.org/10.5281/zenodo.20348942) (`.fafm`) · [Agents](https://doi.org/10.5281/zenodo.21951641) (`.fafa`).

### BibTeX

```bibtex
@article{wolfe2026faf,
  title     = {Format-Driven AI Context Architecture: The .faf Standard for Persistent Project Understanding},
  author    = {Wolfe, James},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.18251362},
  url       = {https://doi.org/10.5281/zenodo.18251362}
}
```

**License**
MIT (this About repo). Source remains private.

If this has been useful, consider starring the repo — it helps others find it.
