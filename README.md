# Rhodesli

A family lineage tool built with FastHTML.

## Architecture: Hybrid (Local Ingestion + Web Interface)

Rhodesli uses a hybrid architecture that separates heavy AI processing from the lightweight web interface:

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              INGESTION PIPELINE (core/)              │   │
│  │  • Face detection & recognition (InsightFace)        │   │
│  │  • Embedding generation                              │   │
│  │  • Heavy GPU/CPU processing                          │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  DATA STORE (data/)                  │   │
│  │  • SQLite database (.db)                             │   │
│  │  • NumPy embeddings (.npy)                           │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              WEB INTERFACE (app/)                    │   │
│  │  • FastHTML server                                   │   │
│  │  • Lightweight queries only                          │   │
│  │  • No heavy AI dependencies                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Why Hybrid?

1. **Separation of Concerns**: Heavy ML dependencies (PyTorch, InsightFace) are isolated from the web server
2. **Lightweight Deployment**: The web app only needs minimal dependencies
3. **Batch Processing**: Ingestion can run as a background job without affecting the web interface
4. **Flexibility**: Process photos locally, then deploy only the web viewer

## Project Structure

```
rhodesli/
├── app/                    # FastHTML web application
│   ├── main.py            # Application entry point
│   └── public/            # Static assets (CSS, images, favicon)
├── core/                   # Heavy AI processing scripts
│   └── (ingestion & inference pipelines)
├── data/                   # Generated embeddings & database
│   └── (*.npy, *.db - gitignored)
├── notebooks/              # Experimental research
├── requirements.txt        # Web dependencies (lightweight)
└── requirements-local.txt  # Ingestion dependencies (heavy)
```

## Getting Started

### Web Interface Only

```bash
pip install -r requirements.txt
python app/main.py
```

### Full Local Development (with AI processing)

```bash
pip install -r requirements.txt
pip install -r requirements-local.txt
```

## Usage

1. **Ingest**: Run scripts in `core/` to process photos and generate embeddings
2. **View**: Start the web server to browse and explore your family lineage
