from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, File
import os, re, json
from groq import Groq
from pydantic import BaseModel
from dotenv import load_dotenv
import pdfplumber, docx
import spacy
from typing import List
import random
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
load_dotenv()
nlp = spacy.load("en_core_web_lg")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class SkillInput(BaseModel):
    skills: list
    level: str = "beginner"
    user: str = 'student'
    interview: str='technical_interview'

class EvaluateAnswerInput(BaseModel):
    skills: List[str]
    question: str
    answer: str

# Groq API helper
def generate_with_groq(prompt):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120
        )
        return response.choices[0].message.content
    except Exception as e:
        print("Groq failed:", e)
        return None

# Supported skill keywords
SKILL_KEYWORDS = [
    "python", "java", "c++", "sql", "html", "css", "javascript",
    "machine learning", "deep learning", "nlp", "pandas", "numpy",
    "react", "node", "django", "flask", "git", "docker"
]

# Extract text from PDF/DOCX
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

# Extract skills
def extract_skills(text):
    text_lower = text.lower()
    found = set([skill for skill in SKILL_KEYWORDS if skill in text_lower])

    # NER extraction
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in ['SKILL', 'TECHNOLOGY', 'PROGRAMMING_LANGUAGE', 'FRAMEWORK', 'Soft_skills', 'Teamwork']:
            found.add(ent.text.lower())
    return list(found)
@app.get("/")
def home():
    return FileResponse("Smart_Interview_page.html")

# Routes
@app.post("/extract_skills")
async def extract_resume_skills(file: UploadFile = File(...)):
    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(file.file)
    elif file.filename.endswith(".docx"):
        text = extract_text_from_docx(file.file)
    else:
        return {"error": "Unsupported file format"}

    skills = extract_skills(text)
    return {"filename": file.filename, "skills": skills}

asked_questions_per_session = {}

@app.post("/generate_questions")
def generate_questions(data: SkillInput):
    skills = random.choice(data.skills)
    level = data.level
    user = data.user
    interview = data.interview

    if interview =='HR_Interview':
        prompt = f"""
You are an experienced HR interviewer.
The user is preparing a behavioral/HR interview.

Generate ONE question based ONLY on this skill: {skills}.

Focus on:
- evaluating soft skills, communication, and teamwork
- situational and behavioral scenarios
- problem-solving approach and attitude
- keeping it professional and concise

Return ONLY the question text.
Do NOT include explanations, examples, numbering, or extra content.
"""
    elif user == 'student':
        prompt = f"""
You are an expert technical interviewer.
The user is a STUDENT preparing for {interview}.

Generate ONE {level} difficulty interview question
based ONLY on this skill: {skills}.

Guidelines:
- For beginner → simple and conceptual.
- For intermediate → practical or scenario-based.
- For advanced → deep, analytical, or industry-grade.
- Make it clear, concise, and easy to understand for a student.

Return ONLY the question text.
Do NOT include explanations, prefixes, numbering, or extra content.
"""
    else:
        prompt = f"""
You are an expert interview coach.
The user is an INTERVIEWER taking a {interview} interview.

Generate ONE high-quality {level} interview question
based ONLY on this skill: {skills}.

Focus on:
- assessing the candidate’s depth of knowledge
- testing problem-solving and critical thinking
- real-world application or scenario-based challenges
- tailoring the question to the interview type (e.g., technical, coding, system design)

Return ONLY the question text.
Do NOT include explanations, examples, numbering, or extra content.
"""

    session_id = "default"  
    if session_id not in asked_questions_per_session:
        asked_questions_per_session[session_id] = []

    previous_questions = asked_questions_per_session[session_id]

    question = generate_with_groq(prompt)

    # Avoid duplicates
    max_attempts = 5
    attempt = 0
    while question in previous_questions and attempt < max_attempts:
        question = generate_with_groq(prompt)
        attempt += 1

    previous_questions.append(question)
    asked_questions_per_session[session_id] = previous_questions

    return {"question": question.strip()}



@app.post("/evaluate_answer")
def evaluate_answer(data: EvaluateAnswerInput):
    prompt = f"""
    You are an expert interviewer.
    Question: {data.question}
    Candidate Answer: {data.answer}
    Evaluate the accuracy on a scale 0-100% and give short feedback.
    Return JSON like: {{ "accuracy": <number>, "feedback": "<text>" }}
    """
    evaluation = generate_with_groq(prompt)
    try:
        match = re.search(r"\{.*\}", evaluation, re.DOTALL)
        result = json.loads(match.group())
    except:
        result = {"accuracy": 0, "feedback": evaluation or "Evaluation failed."}

    return result
