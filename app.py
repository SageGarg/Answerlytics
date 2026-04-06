from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import os
import tempfile
import json
from transcribe import transcribe_answer, analyze_fillers
from evaluator import build_graph, load_resume

app = FastAPI()

# Create static dir if it doesn't exist
os.makedirs("static", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.post("/api/evaluate")
async def evaluate_interview(
    resume: UploadFile = File(...),
    audio: UploadFile = File(...),
    target_company: str = Form(...),
    question: str = Form(...)
):
    resume_path = None
    audio_path = None
    try:
        # Save resume to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_resume:
            tmp_resume.write(await resume.read())
            resume_path = tmp_resume.name
        
        # Save audio to temp file
        # The web audio will likely be webm or ogg or wav, we use a generic placeholder
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_audio:
            tmp_audio.write(await audio.read())
            audio_path = tmp_audio.name

        print("1. Transcribing audio...")
        data = transcribe_answer(audio_path)
        
        print("2. Analyzing fillers...")
        fillers = analyze_fillers(data["transcript"])
        data["fillers"] = fillers
        
        print("3. Loading resume context...")
        data["resume_context"] = load_resume(resume_path)
        data["question"] = question
        data["target_company"] = target_company

        print("4. Running evaluator graph...")
        graph_app = build_graph()
        result = graph_app.invoke(data)

        # Cleanup temp files
        if resume_path and os.path.exists(resume_path):
            os.remove(resume_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)

        return JSONResponse(content={
            "success": True,
            "transcript": result.get("transcript", ""),
            "stats": {
                "word_count": result.get("word_count", 0),
                "duration_seconds": result.get("duration_seconds", 0),
                "words_per_minute": result.get("words_per_minute", 0),
                "fillers": result.get("fillers", {})
            },
            "feedback": result.get("final_feedback", "")
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # Cleanup temp files on error
        if resume_path and os.path.exists(resume_path):
            os.remove(resume_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
            
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
