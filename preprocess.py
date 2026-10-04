#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preprocess.py
=============
Reads every file in the input/ folder (any depth of sub-folders), extracts the
text, optionally computes local semantic-search embeddings, and generates a
fully self-contained chatbot page:

    output/chat.html        chatbot page

All the data is embedded inside the generated pages, so you can open them with
a double click: no server and no internet connection are needed for plain
keyword (BM25) search.

Supported files: .docx  .txt  .md  .pdf (needs pdfplumber)  .xlsx (needs openpyxl)

Usage:
    python preprocess.py

Run it again every time you add or change files in input/.
"""

import os
import re
import json
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CHAT_TEMPLATE_PATH = os.path.join(BASE_DIR, "chat_template.html")
OUTPUT_CHAT_HTML = os.path.join(OUTPUT_DIR, "chat.html")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "index.json")

SUPPORTED_EXT = {".docx", ".txt", ".md", ".pdf", ".xlsx"}

# Local semantic-search model. The exact same name must be used in
# chat_template.html (the browser embeds the user's query with it at search time)
# so that documents and queries live in the same vector space.
LOCAL_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
# Approximate chunk size in characters, and the overlap between neighbouring
# chunks (so a fact sitting on a chunk boundary is not cut in half and lost).
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

# Arabic Unicode block (written as an escape so this source stays ASCII-only).
ARABIC_RE = re.compile("[\u0600-\u06FF]")
LATIN_RE = re.compile(r"[A-Za-z]")


def extract_docx(path):
    import docx
    from docx.oxml.ns import qn

    d = docx.Document(path)
    parts = []
    body = d.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            for p in d.paragraphs:
                if p._p is child:
                    if p.text.strip():
                        parts.append(p.text.strip())
                    break
        elif child.tag == qn("w:tbl"):
            for t in d.tables:
                if t._tbl is child:
                    for row in t.rows:
                        cells = [c.text.strip() for c in row.cells]
                        cells = [c for c in cells if c]
                        if cells:
                            parts.append(" | ".join(cells))
                    break
    return "\n".join(parts)


def extract_txt(path):
    for enc in ("utf-8", "utf-8-sig", "cp1256", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_pdf(path):
    try:
        import pdfplumber
    except ImportError:
        print(f"  [warning] pdfplumber is not installed - skipped: {path}")
        print("  (install it with: python -m pip install pdfplumber)")
        return None
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t.strip())
    return "\n".join(parts)


def extract_xlsx(path):
    """
    Turn a spreadsheet into text, one line per data row.

    Real-world sheets often hold several tables stacked on top of each other,
    each with its own title row and header row, e.g.:

        Express prices            <- title (a lone cell after a blank row)
        Country | 5-10 Kg | ...   <- header row of that table
        Egypt   | 359     | ...   <- data rows
        (blank row)
        Economy prices            <- next table's title
        Country | 5-10 Kg | ...

    Every data row is written as "<sheet> > <table title> | <column>: <value> | ..."
    so each line (and therefore each chunk) is self-describing: the table it
    belongs to and the meaning of every number are never lost when the file is
    split into chunks.
    """
    try:
        import openpyxl
    except ImportError:
        print(f"  [warning] openpyxl is not installed - skipped: {path}")
        print("  (install it with: python -m pip install openpyxl)")
        return None
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        title = ""          # current table title
        headers = None      # current table header row
        expect_header = True
        prev_blank = True
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v).replace("\xa0", " ").strip() for v in row]
            filled = [v for v in vals if v]
            if not filled:
                prev_blank = True
                continue
            if len(filled) == 1 and prev_blank:
                # A lone cell after a blank row starts a new table: it is its title.
                title = filled[0]
                headers = None
                expect_header = True
                prev_blank = False
                continue
            prev_blank = False
            if expect_header and len(filled) >= 2:
                headers = vals
                expect_header = False
                continue
            prefix = ws.title + (" > " + title if title else "")
            cells = []
            for i, v in enumerate(vals):
                if not v:
                    continue
                h = headers[i] if headers and i < len(headers) else ""
                cells.append(f"{h}: {v}" if h else v)
            if cells:
                parts.append(prefix + " | " + " | ".join(cells))
    wb.close()
    return "\n".join(parts)


def extract_text(path, ext):
    if ext == ".docx":
        return extract_docx(path)
    if ext in (".txt", ".md"):
        return extract_txt(path)
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".xlsx":
        return extract_xlsx(path)
    return None


def detect_language(text):
    ar = len(ARABIC_RE.findall(text))
    en = len(LATIN_RE.findall(text))
    if ar == 0 and en == 0:
        return "en"
    return "ar" if ar >= en else "en"


HASH_U_RE = re.compile(r"#U([0-9A-Fa-f]{4})")


def decode_hash_u_encoding(name):
    """
    Some files (especially ones with non-ASCII names) arrive with their names
    escaped as "#U0627#U0644..." instead of the real characters. This happens
    when files are exported/downloaded from some sources: every #Uxxxx stands
    for one Unicode character written in hex. This turns them back into the
    original text.
    """
    if "#U" not in name:
        return name
    try:
        return HASH_U_RE.sub(lambda m: chr(int(m.group(1), 16)), name)
    except ValueError:
        return name


def clean_title(filename_no_ext):
    filename_no_ext = decode_hash_u_encoding(filename_no_ext)
    # Strip common language suffixes such as "(Arabic)", "(English)", "(AR)", "(EN)".
    # The last two alternatives are the Arabic words for "Arabic" and "English".
    t = re.sub(
        r"\s*[\(\[](Arabic|English|AR|EN|\u0639\u0631\u0628\u064a|\u0627\u0646\u062c\u0644\u064a\u0632\u064a)[\)\]]\s*$",
        "", filename_no_ext, flags=re.I)
    return t.strip() or filename_no_ext


def collect_files():
    files = []
    if not os.path.isdir(INPUT_DIR):
        return files
    for root, _dirs, names in os.walk(INPUT_DIR):
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            if ext not in SUPPORTED_EXT:
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, INPUT_DIR)
            rel_parts = rel.split(os.sep)
            category = rel_parts[0] if len(rel_parts) > 1 else "General"
            files.append((full, name, ext, category, rel))
    return files


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Split a document into smaller "chunks" instead of treating it as one unit.
    This solves two problems:
    1) Every chunk gets its own embedding, so semantic search finds exactly the
       part of a long document that answers the question.
    2) When building the context for the AI model we send the right chunk
       (whole, not truncated) instead of the first ~2000 characters of the file.

    The splitter respects paragraphs (it stacks paragraphs until the chunk is
    close to chunk_size); a single paragraph longer than chunk_size is cut by
    characters with an overlap so information on the boundary is not lost.
    """
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    if not paras:
        return [text[:chunk_size]] if text else [""]

    chunks = []
    current = ""
    for p in paras:
        candidate = (current + "\n" + p) if current else p
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(p) <= chunk_size:
            current = p
        else:
            start = 0
            while start < len(p):
                end = start + chunk_size
                chunks.append(p[start:end])
                start = end - overlap
            current = ""
    if current:
        chunks.append(current)
    return chunks or [text[:chunk_size]]


def add_chunks(docs):
    """
    Split every document into chunks (always, with or without embeddings).
    The pages use the chunks to send the AI model only the passage that matches
    the question, instead of the first part of a long file.
    """
    for d in docs:
        d["chunks"] = [{"text": p} for p in chunk_text(d["text"] or " ")]
    return docs


def add_embeddings(docs):
    """
    Split every document into chunks and compute a local embedding (no
    internet, no API key) for each chunk with a free sentence-transformers
    model, storing them in doc["chunks"]. If the library is not installed the
    documents are returned unchanged: keyword (BM25) search keeps working.

    Important: the same model (LOCAL_EMBED_MODEL) must run in the browser
    (chat_template.html) at search time, so that questions and documents are compared in the same
    vector space.
    """
    try:
        from st_loader import load_sentence_transformer
        SentenceTransformer = load_sentence_transformer()
    except ImportError as e:
        print("\n(Skipping embeddings: the sentence-transformers library could not be imported.")
        print(f" Reason: {e}")
        print(" If it is not installed, install it with:")
        print("   python -m pip install sentence-transformers")
        print(" If it IS installed and the reason mentions 'Application Control policy' or 'DLL load failed',")
        print(" Windows is blocking its compiled files: see Troubleshooting in GETTING_STARTED.md.")
        print(" Keyword search (BM25) keeps working without it.)")
        return docs

    print(f"\nLoading the local semantic-search model ({LOCAL_EMBED_MODEL})...")
    print("(The first run downloads the model, about 470 MB; afterwards it is cached on your machine.)")
    try:
        model = SentenceTransformer(LOCAL_EMBED_MODEL)
    except Exception as e:
        print(f"[warning] Could not load the semantic-search model: {e}")
        print("Falling back to keyword search (BM25) only.")
        return docs

    all_chunk_texts = []
    doc_chunk_map = []  # (doc_index, chunk_index_within_doc)
    for di, d in enumerate(docs):
        for ci, c in enumerate(d["chunks"]):
            all_chunk_texts.append(c["text"])
            doc_chunk_map.append((di, ci))

    print(f"Computing embeddings for {len(all_chunk_texts)} chunks locally (no internet or key needed)...")
    try:
        vectors = model.encode(all_chunk_texts, show_progress_bar=True, normalize_embeddings=True)
    except Exception as e:
        print(f"[warning] Embedding generation failed: {e}")
        print("Falling back to keyword search (BM25) only.")
        return docs

    for (di, ci), vec in zip(doc_chunk_map, vectors):
        docs[di]["chunks"][ci]["embedding"] = [round(float(x), 5) for x in vec]

    print("Embeddings generated: semantic search is available in the chat page.")
    print("(The browser embeds your question itself; no server is needed.)")
    return docs


def build_index():
    files = collect_files()
    if not files:
        print(f"No supported files found in: {INPUT_DIR}")
        print(f"Supported formats: {', '.join(sorted(SUPPORTED_EXT))}")
        return []

    docs = []
    doc_id = 0
    for full, name, ext, category, rel in sorted(files, key=lambda x: x[4]):
        print(f"  Processing: {rel}")
        try:
            text = extract_text(full, ext)
        except Exception as e:
            print(f"  [error] Failed to extract text from {rel}: {e}")
            continue
        if not text or not text.strip():
            print(f"  [warning] File is empty or could not be read: {rel}")
            continue
        title_no_ext = os.path.splitext(name)[0]
        doc_id += 1
        display_rel = "/".join(decode_hash_u_encoding(part) for part in rel.replace(os.sep, "/").split("/"))
        docs.append({
            "id": doc_id,
            "title": clean_title(title_no_ext),
            "category": decode_hash_u_encoding(category),
            "language": detect_language(text),
            "file": display_rel,
            "text": text.strip(),
        })
    return docs


def render_page(template_path, output_path, payload):
    if not os.path.exists(template_path):
        print(f"[error] Template file not found: {template_path}")
        sys.exit(1)
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    html = template.replace("/*__KB_DATA__*/[]", payload)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def render_chat(docs):
    payload = json.dumps(docs, ensure_ascii=False)
    payload = payload.replace("</script", "<\\/script")

    if os.path.exists(CHAT_TEMPLATE_PATH):
        render_page(CHAT_TEMPLATE_PATH, OUTPUT_CHAT_HTML, payload)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("Knowledge base preprocessing")
    print("=" * 60)
    docs = build_index()
    if not docs:
        print("\n0 documents extracted - put your files in the input/ folder and run the script again.")
        return
    docs = add_chunks(docs)
    docs = add_embeddings(docs)
    render_chat(docs)
    langs = {}
    cats = {}
    for d in docs:
        langs[d["language"]] = langs.get(d["language"], 0) + 1
        cats[d["category"]] = cats.get(d["category"], 0) + 1

    print("\n" + "-" * 60)
    print(f"Indexed {len(docs)} documents")
    print(f"Languages: {langs}")
    print(f"Categories: {cats}")
    print("-" * 60)
    print(f"\nChatbot ready: {OUTPUT_CHAT_HTML}")
    print("Open it in your browser to start.")


if __name__ == "__main__":
    main()
