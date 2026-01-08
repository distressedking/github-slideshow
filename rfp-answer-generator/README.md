# RFP Answer Generator

An AI-powered application that leverages previous RFP (Request for Proposal) documents and their corresponding answers to generate draft responses for new RFPs.

## Features

- **Document Upload**: Upload RFP-answer document pairs (PDF, DOCX, TXT, MD)
- **Intelligent Search**: Find similar content using vector similarity search
- **Answer Generation**: Generate draft answers based on historical responses
- **Question Extraction**: Automatically extract questions from RFP documents
- **Export Options**: Export generated answers in Markdown or JSON format
- **LLM Enhancement**: Optional integration with OpenAI or Anthropic for improved answers

## Architecture

```
rfp-answer-generator/
├── backend/
│   ├── __init__.py
│   ├── config.py              # Application configuration
│   ├── document_processor.py  # Document text extraction
│   ├── vector_store.py        # Embedding storage and search
│   ├── answer_generator.py    # Answer generation logic
│   └── main.py               # FastAPI application
├── templates/
│   └── index.html            # Web interface
├── static/
│   ├── css/style.css         # Styling
│   └── js/app.js             # Frontend logic
├── data/
│   ├── samples/              # Sample RFP documents
│   ├── uploads/              # Temporary upload storage
│   └── chroma_db/            # Vector database
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
└── README.md                # This file
```

## Installation

### Prerequisites

- Python 3.9+
- pip

### Setup

1. **Clone the repository and navigate to the project:**

```bash
cd rfp-answer-generator
```

2. **Create a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
```

4. **Configure environment (optional):**

```bash
cp .env.example .env
# Edit .env with your settings
```

5. **Run the application:**

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

6. **Open in browser:**

Navigate to `http://localhost:8000`

## Usage

### 1. Upload Document Pairs

Start by uploading your existing RFP documents along with their successful answer documents:

1. Go to the **Upload Documents** tab
2. Select an RFP document (the request/questions)
3. Select the corresponding Answer document (your response)
4. Click **Upload Document Pair**

The more document pairs you upload, the better the answer generation will be.

### 2. Generate Answers

Once you have uploaded reference documents:

**Single Question:**
1. Go to **Generate Answers** tab
2. Select "Single Question" mode
3. Enter your RFP question
4. Click **Generate Answer**

**Multiple Questions:**
1. Select "Multiple Questions" mode
2. Enter questions (one per line)
3. Click **Generate All Answers**

**From File:**
1. Select "From File" mode
2. Upload a new RFP document
3. Questions will be automatically extracted and answered

### 3. Export Results

After generating answers:
- Click **Export Markdown** for formatted document
- Click **Export JSON** for structured data
- Click **Copy All** to copy to clipboard

### 4. Search Documents

Use the **Search** tab to find specific content in your uploaded documents:
- Search by keywords or phrases
- Filter by document type (RFP or Answer)
- View matching content with similarity scores

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web interface |
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Database statistics |
| POST | `/api/upload/pair` | Upload RFP-answer pair |
| POST | `/api/upload/single` | Upload single document |
| POST | `/api/generate/answer` | Generate single answer |
| POST | `/api/generate/bulk` | Generate multiple answers |
| POST | `/api/generate/from-file` | Extract questions and generate |
| POST | `/api/search` | Search documents |
| GET | `/api/pairs` | List document pairs |
| DELETE | `/api/document/{filename}` | Delete document |
| POST | `/api/clear` | Clear all documents |

## LLM Enhancement (Optional)

For higher quality answer generation, you can enable LLM integration:

1. Set `USE_LLM=true` in your `.env` file
2. Add your API key:
   - For OpenAI: `OPENAI_API_KEY=your-key`
   - For Anthropic: `ANTHROPIC_API_KEY=your-key`
3. Set the provider: `LLM_PROVIDER=openai` or `LLM_PROVIDER=anthropic`

Without LLM, the system uses similarity-based answer generation which works well for finding and adapting existing answers.

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | true | Enable debug mode |
| `USE_LLM` | false | Enable LLM-enhanced generation |
| `LLM_PROVIDER` | openai | LLM provider (openai/anthropic) |
| `TOP_K_RESULTS` | 5 | Number of similar docs to retrieve |
| `SIMILARITY_THRESHOLD` | 0.3 | Minimum similarity score |
| `CHUNK_SIZE` | 1000 | Document chunk size in characters |
| `CHUNK_OVERLAP` | 200 | Overlap between chunks |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | Sentence transformer model |

## Sample Data

The `data/samples/` directory contains example RFP and answer documents:

- `sample_rfp_1.txt` - Enterprise software development RFP
- `sample_answer_1.txt` - Corresponding answer document
- `sample_rfp_2.txt` - Cloud migration services RFP
- `sample_answer_2.txt` - Corresponding answer document

Upload these to test the system.

## How It Works

1. **Document Processing**: Documents are parsed and split into overlapping chunks for better context preservation.

2. **Embedding Generation**: Each chunk is converted to a vector embedding using sentence transformers.

3. **Vector Storage**: Embeddings are stored in ChromaDB with metadata linking RFPs to their answers.

4. **Similarity Search**: When generating answers, the system finds the most similar chunks to the question.

5. **Answer Generation**: Relevant previous answers are retrieved and synthesized into a draft response.

6. **LLM Enhancement** (optional): An LLM can be used to create more polished, contextually-aware responses.

## Tips for Best Results

1. **Quality Training Data**: Upload high-quality, successful RFP responses
2. **Document Pairs**: Always upload RFPs with their corresponding answers
3. **Diverse Content**: Include RFPs from different industries and types
4. **Review Generated Answers**: Always review and customize generated drafts
5. **Update Regularly**: Add new successful responses to improve quality

## Troubleshooting

**Empty results when generating answers:**
- Ensure you have uploaded document pairs first
- Check that the question is similar to content in your documents

**Slow first query:**
- The embedding model is loaded on first use
- Subsequent queries will be faster

**Import errors:**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Use Python 3.9 or higher

## License

MIT License - feel free to use and modify for your needs.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
