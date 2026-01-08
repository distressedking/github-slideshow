"""
RFP Answer Generator - Main FastAPI Application
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.requests import Request

from .config import settings
from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from .answer_generator import AnswerGenerator


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Generate RFP answers using AI-powered document analysis"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = settings.BASE_DIR / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Setup templates
templates_path = settings.BASE_DIR / "templates"
templates_path.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_path))

# Initialize services
document_processor = DocumentProcessor(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP
)
vector_store = VectorStore()
answer_generator = AnswerGenerator(vector_store)


# Pydantic Models
class QuestionRequest(BaseModel):
    question: str
    use_llm: Optional[bool] = False
    top_k: Optional[int] = 5


class MultiQuestionRequest(BaseModel):
    questions: List[str]
    use_llm: Optional[bool] = False


class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    document_type: Optional[str] = None


# API Routes

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main application page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/api/stats")
async def get_stats():
    """Get vector store statistics"""
    try:
        stats = vector_store.get_stats()
        return stats
    except Exception as e:
        return {"error": str(e), "total_chunks": 0, "pairs": 0}


@app.post("/api/upload/pair")
async def upload_document_pair(
    rfp_file: UploadFile = File(..., description="RFP document"),
    answer_file: UploadFile = File(..., description="Answer document")
):
    """Upload an RFP and its corresponding answer document"""

    # Validate file types
    allowed_extensions = {'.pdf', '.docx', '.txt', '.md'}

    for file in [rfp_file, answer_file]:
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}"
            )

    try:
        # Save uploaded files temporarily
        rfp_path = settings.UPLOAD_DIR / f"rfp_{rfp_file.filename}"
        answer_path = settings.UPLOAD_DIR / f"answer_{answer_file.filename}"

        with open(rfp_path, "wb") as f:
            shutil.copyfileobj(rfp_file.file, f)

        with open(answer_path, "wb") as f:
            shutil.copyfileobj(answer_file.file, f)

        # Process documents
        rfp_doc = document_processor.process_document(str(rfp_path), "rfp")
        answer_doc = document_processor.process_document(str(answer_path), "answer")

        # Add to vector store
        result = vector_store.add_document_pair(rfp_doc, answer_doc)

        # Clean up temp files
        rfp_path.unlink()
        answer_path.unlink()

        return {
            "success": True,
            "message": "Document pair uploaded and indexed successfully",
            "details": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload/single")
async def upload_single_document(
    file: UploadFile = File(...),
    document_type: str = Form(..., description="'rfp' or 'answer'")
):
    """Upload a single document"""

    if document_type not in ['rfp', 'answer']:
        raise HTTPException(status_code=400, detail="document_type must be 'rfp' or 'answer'")

    allowed_extensions = {'.pdf', '.docx', '.txt', '.md'}
    ext = Path(file.filename).suffix.lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}"
        )

    try:
        # Save uploaded file temporarily
        file_path = settings.UPLOAD_DIR / f"{document_type}_{file.filename}"

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Process document
        doc = document_processor.process_document(str(file_path), document_type)

        # Add to vector store
        result = vector_store.add_single_document(doc)

        # Clean up
        file_path.unlink()

        return {
            "success": True,
            "message": f"{document_type.upper()} document uploaded and indexed",
            "details": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/answer")
async def generate_answer(request: QuestionRequest):
    """Generate an answer for a single question"""

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = answer_generator.generate_answer(
            question=request.question,
            use_llm=request.use_llm,
            top_k=request.top_k
        )

        return {
            "question": result.question,
            "answer": result.answer,
            "confidence_score": result.confidence_score,
            "sources": result.sources,
            "method": result.method
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/bulk")
async def generate_bulk_answers(request: MultiQuestionRequest):
    """Generate answers for multiple questions"""

    if not request.questions:
        raise HTTPException(status_code=400, detail="Questions list cannot be empty")

    try:
        results = answer_generator.generate_full_rfp_response(
            questions=request.questions,
            use_llm=request.use_llm
        )

        return {
            "count": len(results),
            "answers": [{
                "question": r.question,
                "answer": r.answer,
                "confidence_score": r.confidence_score,
                "sources": r.sources,
                "method": r.method
            } for r in results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/from-file")
async def generate_from_file(
    file: UploadFile = File(..., description="RFP document to generate answers for"),
    use_llm: bool = Form(False)
):
    """Upload an RFP and generate answers for extracted questions"""

    allowed_extensions = {'.pdf', '.docx', '.txt', '.md'}
    ext = Path(file.filename).suffix.lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}"
        )

    try:
        # Save uploaded file temporarily
        file_path = settings.UPLOAD_DIR / f"query_{file.filename}"

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Process and extract questions
        doc = document_processor.process_document(str(file_path), "rfp")
        questions = document_processor.extract_questions_from_rfp(doc.full_text)

        # Clean up
        file_path.unlink()

        if not questions:
            return {
                "success": False,
                "message": "No questions could be extracted from the document",
                "full_text_preview": doc.full_text[:1000] + "..."
            }

        # Generate answers for extracted questions
        question_texts = [q['question'] for q in questions]
        results = answer_generator.generate_full_rfp_response(
            questions=question_texts,
            use_llm=use_llm
        )

        return {
            "success": True,
            "extracted_questions": len(questions),
            "answers": [{
                "question": r.question,
                "answer": r.answer,
                "confidence_score": r.confidence_score,
                "sources": r.sources,
                "method": r.method
            } for r in results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search_documents(request: SearchRequest):
    """Search for similar documents"""

    try:
        results = vector_store.search_similar(
            query=request.query,
            top_k=request.top_k,
            document_type=request.document_type
        )

        return {
            "query": request.query,
            "results": [{
                "content": r.content,
                "source_file": r.source_file,
                "document_type": r.document_type,
                "similarity_score": r.similarity_score,
                "answer_content": r.answer_content
            } for r in results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pairs")
async def get_document_pairs():
    """Get all RFP-Answer document pairs"""

    try:
        pairs = vector_store.get_all_pairs()
        return {"pairs": pairs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/document/{filename}")
async def delete_document(filename: str):
    """Delete a document from the vector store"""

    try:
        deleted_count = vector_store.delete_by_source(filename)
        return {
            "success": True,
            "message": f"Deleted {deleted_count} chunks from {filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clear")
async def clear_vector_store():
    """Clear all documents from the vector store"""

    try:
        vector_store.clear_all()
        return {"success": True, "message": "All documents cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export")
async def export_answers(
    request: MultiQuestionRequest,
    format: str = Query("markdown", description="Export format: markdown, json, or plain")
):
    """Generate and export answers in the specified format"""

    try:
        results = answer_generator.generate_full_rfp_response(
            questions=request.questions,
            use_llm=request.use_llm
        )

        exported = answer_generator.export_response(results, format=format)

        return {
            "format": format,
            "content": exported
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run with: uvicorn backend.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
