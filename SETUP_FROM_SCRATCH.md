# Setup From Scratch

This guide is for someone who wants to run the chatbot for the first time on a new machine.

It covers:

1. what you need before starting
2. how to install dependencies
3. how to add teaching materials
4. how to build the search index
5. how to start the chatbot
6. how to update it later

## 1. What This Project Does

This chatbot answers questions using only files placed in `src/`.

It does not use web search or outside knowledge. It searches the local teaching materials, finds relevant text, and answers with citations.

Main project folders:

- `src/`: your teaching materials
- `data/`: saved search index
- `app/`: chatbot code and web app
- `run_local.py`: easiest way to run the system locally
- `install.py`: optional helper installer

## 2. Requirements

Before starting, make sure you have:

- Python 3.12
- Conda
- enough disk space for Python packages and your documents

Optional:

- Ollama, if you want more natural Thai answers

Recommended current environment name in this project:

```bash
shapash312
```

## 3. Open the Project Folder

Open a terminal in this project folder:

```bash
/mnt/c/Users/sarun/OneDrive/works/edu/thesis/Sinatta
```

If you are using Windows with Conda, open Anaconda Prompt or PowerShell first, then go to the project folder.

## 4. Create the Python Environment

If you do not already have the Conda environment:

```bash
conda create -n shapash312 python=3.12 -y
```

Then activate it:

```bash
conda activate shapash312
```

If the environment already exists, just activate it:

```bash
conda activate shapash312
```

## 5. Install Python Packages

Install the required packages:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you prefer not to activate the environment first, use:

```bash
conda run -n shapash312 python -m pip install --upgrade pip
conda run -n shapash312 python -m pip install -r requirements.txt
```

## 6. Optional: Use the Helper Installer

If you want the project to install Python dependencies for you, you can use:

```bash
python install.py
```

Or for Ollama mode:

```bash
python install.py --backend ollama
```

Notes:

- on Windows, Ollama must usually be installed manually
- the helper installer is optional, not required

## 7. Optional: Install Ollama for Better Natural Answers

If you want the chatbot to sound more natural and more like a teacher explaining in class, install Ollama and pull a local model.

Example model:

```bash
ollama pull llama3.1:8b
```

If you do not install Ollama, the chatbot can still run in `extractive` mode.

Difference:

- `extractive`: more rigid, more direct from retrieved text
- `ollama`: more natural Thai phrasing, but still constrained to the retrieved documents

## 8. Add Your Teaching Materials

Create or use the `src/` folder and place your documents inside it.

Example:

```text
src/
  technology/
    unit1.pdf
    unit2.pdf
  science/
    notes.md
  handbook.docx
```

Supported file types:

- `.txt`
- `.md`
- `.pdf`
- `.docx`

Important rules:

- only put documents in `src/` that you want the chatbot to use
- avoid unrelated files
- if you add poor-quality OCR PDFs, answer quality may drop

## 9. Build the Search Index

After putting files into `src/`, build the local index:

```bash
python -m app.ingest
```

Or:

```bash
conda run -n shapash312 python -m app.ingest
```

This creates:

```text
data/index.pkl
```

The chatbot cannot answer properly until this step is complete.

## 10. Start the Chatbot

The recommended command is:

```bash
python run_local.py
```

Or:

```bash
conda run -n shapash312 python run_local.py
```

This will:

1. rebuild the index unless you tell it not to
2. start the FastAPI server
3. open the chatbot at:

```text
http://127.0.0.1:8000
```

## 11. Start in Ollama Mode

If Ollama is installed and the model is ready:

```bash
python run_local.py --backend ollama --model llama3.1:8b
```

Or:

```bash
conda run -n shapash312 python run_local.py --backend ollama --model llama3.1:8b
```

Use this if you want answers that sound more like a teacher explaining to students.

## 12. What `--skip-ingest` Means

Normally, `run_local.py` rebuilds the index before starting.

If you run:

```bash
python run_local.py --skip-ingest
```

the app starts without rebuilding `data/index.pkl`.

Use `--skip-ingest` when:

- you did not change files in `src/`
- you only changed code such as `app/chatbot.py`
- you want faster startup

Do not use `--skip-ingest` when:

- you added new documents
- you removed documents
- you replaced documents
- you changed ingestion or retrieval logic

## 13. First-Time Test

Once the server is running:

1. open `http://127.0.0.1:8000`
2. ask a simple question related to your documents
3. check whether the answer shows citations
4. check the status label

Status labels:

- `ตอบได้จากเอกสาร`: the answer is supported by the indexed documents
- `ข้อมูลจากเอกสารยังไม่พอ`: the chatbot did not find enough support in `src/`

## 14. Example API Test

You can also test the backend directly:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"การออกแบบชิ้นงานแบบ 3 มิติคืออะไร"}'
```

## 15. When You Must Rebuild the Index

Run this again:

```bash
python -m app.ingest
```

whenever you:

- add files to `src/`
- remove files from `src/`
- replace files in `src/`
- change chunking or retrieval code

You usually do not need to rebuild the index when you only change:

- answer formatting
- prompt wording
- teacher-style response logic in `app/chatbot.py`

## 16. Common Problems

### The chatbot says the search index is missing or outdated

Run:

```bash
python -m app.ingest
```

### The chatbot answers `ข้อมูลจากเอกสารยังไม่พอ`

Possible reasons:

- the answer is not in your documents
- the wording of the question does not match the document language well
- the source documents have weak OCR text

Try:

- adding more relevant documents
- asking a narrower question
- improving document quality

### Port 8000 is already in use

Run on another port:

```bash
python run_local.py --port 8010
```

### Ollama mode does not work

Check:

- Ollama is installed
- the Ollama app or service is running
- the model exists locally

Try:

```bash
ollama pull llama3.1:8b
```

Then run:

```bash
python run_local.py --backend ollama --model llama3.1:8b
```

## 17. Recommended Daily Workflow

For normal use:

1. add or update files in `src/`
2. run `python -m app.ingest`
3. run `python run_local.py --backend ollama --model llama3.1:8b`
4. open the browser and test a few questions

If you only changed chatbot wording or answer style:

1. skip re-ingest
2. run `python run_local.py --skip-ingest`

## 18. Minimal Commands Summary

From zero:

```bash
conda create -n shapash312 python=3.12 -y
conda activate shapash312
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m app.ingest
python run_local.py
```

Better teacher-style mode:

```bash
conda activate shapash312
ollama pull llama3.1:8b
python -m app.ingest
python run_local.py --backend ollama --model llama3.1:8b
```
