# Knowledge Search

Search and chat over your own documents, running entirely in the browser.

Drop your files (`.docx`, `.xlsx`, `.pdf`, `.txt`, `.md`) into `input/`, run one script, and get a
self-contained web page:

- **`output/chat.html`** - a ChatGPT-style chatbot that answers from your documents and shows which
  files (and which exact passage) each answer came from.

It works with **Arabic and English** documents (Arabic-aware text normalisation is built in), and it
is generic: it is not tied to any particular knowledge base.

> New here? Read **[GETTING_STARTED.md](GETTING_STARTED.md)** for step-by-step setup.

---

## How it works

```
 input/                    preprocess.py                         output/
 your documents  --->  1. extract text from each file  --->  chat.html
 (.docx .xlsx .pdf     2. split into ~900-char chunks        chat.html
  .txt .md)            3. (optional) embed every chunk       index.json
                       4. inline everything into the pages
                                                 |
                                                 v
                                          open in a browser
```

### 1. Keyword search (always on, fully offline)

All data is embedded inside the generated HTML, and ranking runs in JavaScript in your browser using
**BM25** (the classic search-engine relevance formula), with:

- Arabic normalisation (removes diacritics, unifies alef / yaa / taa-marbuta forms, strips the "al-" prefix),
- a boost for matches in the document title / category,
- stop-word removal and substring fallback matching.

No server, no internet, no API key.

### 2. Semantic search (optional, local, free)

Keyword search only matches words. Semantic search matches **meaning** (so "do you have an account
for young people?" can find a file named "Youth Account").

- At build time, `preprocess.py` splits every document into chunks and computes an embedding per
  chunk with the open-source model `paraphrase-multilingual-MiniLM-L12-v2` (runs on your machine).
- At search time, the browser embeds your question itself (Transformers.js, same model, quantised) and
  compares it with the chunk embeddings (cosine similarity). No server is needed. The first use
  downloads the library and the model (~120 MB) once; the browser then caches them. If loading fails,
  the page falls back to keyword search.
- Final score = `0.55 x semantic similarity + 0.45 x normalised BM25`, so exact keyword hits still count.

### 3. Smart answers - RAG (optional)

When enabled, the page sends the **most relevant chunk** of each of the top documents (not the whole
file) to an LLM (via [Groq](https://console.groq.com), free tier) and asks it to answer **only from
those excerpts**.

To keep answers trustworthy:

- **Chunking** - the model receives the passage that actually matches the question, even if it sits
  deep inside a long document or a big spreadsheet. Chunks are always created (embeddings are optional);
  the best chunk is picked by rare-word matching (words that appear in few chunks, such as a country
  name, count more than words found everywhere).
- **Relevance cut-off** - documents whose score is far below the best hit are never sent to the model.
- **Cited sources only** - the file chips under an answer are only the files the model named in its
  `Source:` line.
- **Click a source** - opens the file with the exact passage that was sent to the model highlighted,
  so you can verify the answer is grounded in your documents and not invented.

---

## Quick start

```bash
git clone <this-repo>
cd knowledge-search

python -m pip install -r requirements.txt     # installs everything (incl. semantic search)
python preprocess.py                          # build the pages (a small sample is included)
```

Then open `output/chat.html` in your browser. On Windows you can also
double-click `run.bat`; on macOS / Linux run `./run.sh`.

To add your own documents, put them in `input/` (sub-folders become **categories**) and run
`python preprocess.py` again.

### Semantic search

It is included: `requirements.txt` installs `sentence-transformers`, and `python preprocess.py` computes
the document embeddings (the first run downloads a ~470 MB model).

When you open the page, Semantic search is on by default (Settings -> **Enable semantic search**). The
status line shows when the in-browser model is loading or ready.

### Enable smart answers (optional)

1. Create a free API key at <https://console.groq.com/keys>.
2. Open the page -> Settings -> paste the key -> turn on **Enable smart answer** -> Save.

The key is stored only in your browser (`localStorage`) and sent straight to Groq. If your browser
cannot reach Groq directly (CORS error), run `python groq_proxy.py` and put
`http://localhost:8787` under *Advanced settings -> Local proxy URL*.

---

## Project structure

| Path | Purpose |
|---|---|
| `input/` | Your documents. Sub-folders become categories. `input/sample/` holds a tiny demo set. |
| `preprocess.py` | Extracts text, chunks it, computes embeddings, generates the pages. |
| `chat_template.html` | Template of the chatbot page. |
| `st_loader.py` | Imports sentence-transformers; falls back to a stand-in for scikit-learn if Windows blocks it. |
| `groq_proxy.py` | Optional local proxy for the Groq API (only if the browser is blocked by CORS). |
| `output/` | Generated pages and `index.json` (not committed: it contains your document text). |
| `requirements.txt` | All Python dependencies (docx, xlsx, pdf, semantic embeddings). |
| `run.bat` / `run.sh` | One-click build + open. |

## Supported file types

| Type | Notes |
|---|---|
| `.docx` | Paragraphs and tables. |
| `.xlsx` | Every sheet. Several tables stacked in one sheet are detected (a lone title cell after a blank row, then a header row). Each data row becomes one self-describing line: `Sheet > Table title \| Column: value \| Column: value`. |
| `.pdf` | Needs `pdfplumber` (text PDFs only; scanned PDFs need OCR first). |
| `.txt`, `.md` | UTF-8 (falls back to common legacy encodings). |

## Configuration

Constants at the top of `preprocess.py`:

| Constant | Default | Meaning |
|---|---|---|
| `CHUNK_SIZE` | `900` | Approximate characters per chunk. |
| `CHUNK_OVERLAP` | `150` | Overlap between neighbouring chunks. |
| `LOCAL_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Embedding model. If you change it, also change the model name in `chat_template.html`, then rebuild. |

## Troubleshooting

See the troubleshooting section of [GETTING_STARTED.md](GETTING_STARTED.md).

## Privacy and security

- Everything runs locally. Documents never leave your machine, **except** the excerpts sent to Groq
  when you ask for a smart answer.
- The generated pages contain the full text of your documents: do not publish `output/` if the
  documents are confidential (it is git-ignored by default, and so is everything in `input/`
  except `input/sample/`).
- Your API key lives in your browser's `localStorage`; never commit it.
