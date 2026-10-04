# Getting started

Everything you need to run this project for the first time.

## 1. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| **Python 3.9+** (3.10-3.12 recommended) | Runs the build script | `python --version` |
| **pip** (comes with Python) | Installs libraries | `python -m pip --version` |
| A modern browser (Chrome, Edge, Firefox, Safari) | Opens the generated pages | |
| ~1 GB free disk, internet **only once** | Only for semantic search: model + libraries | |
| A free [Groq](https://console.groq.com/keys) API key | Only for AI answers | |

Windows: install Python from <https://www.python.org/downloads/> and tick **"Add python.exe to PATH"**.

## 2. Install the dependencies

From the project folder:

```bash
python -m pip install -r requirements.txt
```

(Optional but recommended: use a virtual environment first -
`python -m venv .venv`, then `.venv\Scripts\activate` on Windows or `source .venv/bin/activate` on
macOS / Linux.)

## 3. Add your documents

Copy your files into `input/`. Sub-folders become categories, for example:

```
input/
  Accounts/Savings.docx
  Cards/Credit Cards.docx
  Fees/Fees.xlsx
```

A tiny sample set is already in `input/sample/` so you can try the project immediately.

## 4. Build the pages

```bash
python preprocess.py
```

You should see a line per file, then a summary (number of documents, languages, categories) and the
path of `output/chat.html`. Re-run it whenever you add or change files.

## 5. Open and search

Open `output/chat.html` in your browser (or double-click `run.bat` on Windows, run
`./run.sh` on macOS / Linux). Keyword search works immediately, offline.

## 6. Semantic search

Nothing extra to install: step 2 already installed `sentence-transformers`. When you run
`python preprocess.py` (step 4) it computes the document embeddings; the first run downloads a
~470 MB model.

Open the page: your questions are embedded in the browser itself, no server needed. The first
time it needs internet once to download the library and the ~120 MB model (cached afterwards).

## 7. (Optional) Smart answers

1. Get a free key at <https://console.groq.com/keys>.
2. In the page: Settings -> paste the key -> **Enable smart answer** -> Save.
3. Type a question and press **Enter**.

## Troubleshooting

**`ModuleNotFoundError: No module named 'docx'`** - run `python -m pip install -r requirements.txt`.

**`No module named 'preprocessors'` / wrong command** - the script is `preprocess.py`; run
`python preprocess.py` from inside the project folder (not `python -m ...`).

**The Excel / PDF file is skipped** - install `openpyxl` / `pdfplumber` (both are in
`requirements.txt`). The script prints a warning naming the skipped file.

**`sentence-transformers` is "not installed" even though you installed it** - you probably have more
than one Python. Check `python -c "import sys; print(sys.executable)"` and install with that same
interpreter: `python -m pip install sentence-transformers`.

**`DLL load failed ... An Application Control policy has blocked this file` (Windows)** - Windows
Smart App Control / Application Control is blocking compiled libraries (scikit-learn, used by
sentence-transformers). Add the project folder to the Windows Security exclusions
(Windows Security -> Virus & threat protection -> Manage settings -> Add or remove exclusions ->
Add the folder), then retry. The project also ships a fallback (`st_loader.py`): if only scikit-learn is blocked, it
loads the embedding model with a small stand-in for scikit-learn, which semantic search does not need, and prints a note.
If the block hits other libraries (torch, numpy), see the next paragraph. If your computer is managed by an organisation you may need IT to allow it.

**Semantic search stays on keyword mode** - the browser could not download the model (needs internet
once, and access to cdn.jsdelivr.net and huggingface.co). Check the connection and reload.

**"Failed to fetch" / CORS error for smart answers** - run `python groq_proxy.py` and set
`http://localhost:8787` in Settings -> Advanced settings -> Local proxy URL.

**HTTP 401 / 403** - the Groq API key is wrong or expired. **HTTP 429** - free-tier rate limit; wait
a minute.

**An answer says the information is not in the knowledge base** - click the source chips to see the
exact passage that was sent to the model. If the right passage is missing, rephrase the question
with words that appear in the documents, or enable semantic search.

**Arabic file names look garbled (`#U0627...`)** - the script decodes these automatically. When
zipping files on Windows, use a tool that stores UTF-8 names.