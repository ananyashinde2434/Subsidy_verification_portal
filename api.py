from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os, shutil, uuid

from backend import process_document

app = FastAPI(
    title="Subsidy Document Verification API",
    description="Validates bank statements and transaction receipts",
    version="1.0.0"
)

# CORS first
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend API is running"}


@app.post("/validate-document")
async def validate_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
        raise HTTPException(status_code=400, detail="Only image or PDF files allowed")

    file_id = str(uuid.uuid4())
    temp_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    await file.close()

    try:
        result = process_document(temp_path)
        return {"success": True, "data": result}

    except Exception as e:
        return {
            "success": False,
            "error": "Document processing failed",
            "details": str(e)
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
