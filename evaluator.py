import json
import os
from typing import TypedDict
from PyPDF2 import PdfReader
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from knowledgeBase import get_company_context

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class InterviewState(TypedDict):
    transcript: str
    word_count: int
    duration_seconds: float
    words_per_minute: float
    fillers: dict
    resume_context: str
    question: str
    target_company: str        # NEW
    company_context: str
    content_feedback: str
    delivery_feedback: str
    final_feedback: str

def load_resume(filepath: str) -> str:
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text.strip()

def fetch_company_context(state: InterviewState) -> InterviewState:
    print(f"Fetching {state['target_company']} interview intel...")
    state["company_context"] = get_company_context(
        state["target_company"], 
        state["question"]
    )
    return state

def evaluate_content(state: InterviewState) -> InterviewState:
    print("Evaluating content...")

    prompt = f"""You are an expert technical recruiter at a top AI company like Anthropic or Microsoft.

CANDIDATE'S ACTUAL RESUME:
{state['resume_context']}

INTERVIEW QUESTION ASKED:
"{state['question']}"

CANDIDATE'S ACTUAL ANSWER:
"{state['transcript']}"

IMPORTANT RULES:
- Only reference projects, experiences, and skills that actually appear in their resume
- Never invent numbers, achievements, or experiences they didn't mention
- "Tell me about yourself" should cover: their story/journey, 1-2 specific real projects with real impact, what drives them toward AI, and why this role
- It should feel human and compelling, not like a resume reading

Evaluate:
1. Did they reference their REAL strongest projects? (check resume)
2. Did they tell a compelling story or just list facts?
3. Did they connect their passion to the work?
4. Was it too short? (ideal 60-90 seconds)

Give 3 specific improvements using ONLY what's actually on their resume."""

    response = llm.invoke(prompt)
    state["content_feedback"] = response.content
    return state

def evaluate_delivery(state: InterviewState) -> InterviewState:
    print("Evaluating delivery...")

    filler_summary = ", ".join([f"'{w}' ({c}x)" 
                                for w, c in state["fillers"].items()]) or "none detected"

    prompt = f"""You are a speech coach for technical interviews.

QUESTION: "{state['question']}"

CANDIDATE STATS:
- Words per minute: {state['words_per_minute']} (ideal: 130-150)
- Duration: {state['duration_seconds']} seconds (ideal for this question: 60-90 seconds)
- Filler words: {filler_summary}
- Word count: {state['word_count']} (ideal: 150-200 words)

TRANSCRIPT: "{state['transcript']}"

Give specific delivery coaching:
1. Pace — too fast, slow, or right?
2. Length — way too short, too long, or right?
3. Confidence signals — do they sound sure of themselves?
4. One specific drill they can do TODAY to improve"""

    response = llm.invoke(prompt)
    state["delivery_feedback"] = response.content
    return state

def synthesize_feedback(state: InterviewState) -> InterviewState:
    print("Synthesizing final feedback...")

    prompt = f"""You are a senior interview coach. Combine the feedback below into one clear, 
direct coaching summary. Be encouraging but honest.

RESUME AVAILABLE: {state['resume_context'][:500]}...

CONTENT FEEDBACK: {state['content_feedback']}
DELIVERY FEEDBACK: {state['delivery_feedback']}
COMPANY-SPECIFIC INTEL FOR {state['target_company']}:
{state['company_context']}

STRICT RULES FOR THE REWRITE:
- The suggested rewrite must ONLY use real projects and experiences from their resume
- Do not invent any metrics or achievements
- The rewrite should sound like a real human, not a robot
- It should tell a story: journey → specific real project → passion → why this role

Format exactly like this:

SCORE: X/10

TOP 3 THINGS TO FIX:
1. [specific, actionable, based on their real resume]
2. [specific, actionable]
3. [specific, actionable]

WHAT YOU DID WELL:
[honest positives]

SUGGESTED REWRITE (using ONLY your real experience):
[rewrite here — should be 150-180 words, human, story-driven]"""

    response = llm.invoke(prompt)
    state["final_feedback"] = response.content
    return state

def build_graph():
    graph = StateGraph(InterviewState)
    graph.add_node("fetch_company_context", fetch_company_context)  # NEW
    graph.add_node("evaluate_content", evaluate_content)
    graph.add_node("evaluate_delivery", evaluate_delivery)
    graph.add_node("synthesize_feedback", synthesize_feedback)
    graph.set_entry_point("fetch_company_context")                   # CHANGED
    graph.add_edge("fetch_company_context", "evaluate_content")      # NEW
    graph.add_edge("evaluate_content", "evaluate_delivery")
    graph.add_edge("evaluate_delivery", "synthesize_feedback")
    graph.add_edge("synthesize_feedback", END)
    return graph.compile()

if __name__ == "__main__":
    with open("transcription_result.json", "r") as f:
        data = json.load(f)

    # Load resume as plain text
    data["resume_context"] = load_resume("resume.pdf")
    
    # Set the question being practiced
    data["question"] = "Tell me about yourself"
    data["target_company"] = "Anthropic"  # Change this to test different companies

    app = build_graph()
    result = app.invoke(data)

    print("\n" + "="*50)
    print("INTERVIEW COACH FEEDBACK")
    print("="*50)
    print(result["final_feedback"])
    
    # Save full result
    with open("feedback_result.json", "w") as f:
        json.dump({
            "question": result["question"],
            "transcript": result["transcript"],
            "stats": {
                "wpm": result["words_per_minute"],
                "duration": result["duration_seconds"],
                "fillers": result["fillers"]
            },
            "feedback": result["final_feedback"]
        }, f, indent=2)
    print("\nSaved to feedback_result.json")