import streamlit as st
import PyPDF2
import pdfplumber
from docx import Document
import google.generativeai as genai
import os
import re

# Function to extract text from files
def extract_text(file):
    if file.name.endswith(".pdf"):
        try:
            with pdfplumber.open(file) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages if page.extract_text()])
            if not text.strip():
                return "Error: No text extracted from PDF (pdfplumber)"
            return text
        except Exception as e:
            st.warning(f"pdfplumber failed: {e}. Falling back to PyPDF2.")
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(reader.pages)):
                extracted = reader.pages[page_num].extract_text() or ""
                if extracted.strip():
                    text += extracted + "\n"
            if not text.strip():
                return "Error: No text extracted from PDF (PyPDF2)"
            return text
    elif file.name.endswith(".docx"):
        doc = Document(file)
        text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        return text
    return "Error: Please use a .pdf or .docx file"

# Function to parse Gemini response
def parse_response(response_text):
    summary_lines = []
    flashcards = []
    current_question = ""
    current_answer = ""

    parsing_state = "start" # Possible states: 'start', 'summary', 'flashcards'

    lines = response_text.splitlines()

    for line in lines:
        line = line.strip()
        if not line: # Skip empty lines
            continue

        # State Transitions
        if parsing_state == "start" and line.lower().startswith("summary:"):
            parsing_state = "summary"
            # Capture text on the same line as "Summary:", if any
            summary_part = line.split(":", 1)[1].strip()
            if summary_part:
                summary_lines.append(summary_part)
            continue # Move to the next line

        if parsing_state == "summary" and line.lower().startswith("flashcards:"):
            parsing_state = "flashcards"
            continue # Move to the next line

        # Content Processing based on State
        if parsing_state == "summary":
            summary_lines.append(line) # Append the whole line

        elif parsing_state == "flashcards":
            # Use regex for more robust matching (case-insensitive)
            question_match = re.match(r"-?\s*question:", line, re.IGNORECASE)
            answer_match = re.match(r"-?\s*answer:", line, re.IGNORECASE)

            if question_match:
                # Store previous flashcard before starting a new one
                if current_question and current_answer:
                    flashcards.append({
                        "question": current_question,
                        "answer": current_answer
                    })
                    current_answer = "" # Reset answer

                # Extract new question
                current_question = line[question_match.end():].strip()

            elif answer_match and current_question: # Only capture answer if we have a question
                 # Append to answer if it spans multiple lines potentially (or just assign)
                answer_part = line[answer_match.end():].strip()
                if current_answer:
                    current_answer += "\n" + answer_part # Append if needed, adjust logic if answers are single line
                else:
                    current_answer = answer_part

            elif current_answer: # Append continuation lines to the current answer
                current_answer += "\n" + line


    # Append the last flashcard if it exists
    if current_question and current_answer:
        flashcards.append({
            "question": current_question,
            "answer": current_answer
        })

    # Join summary lines
    final_summary = "\n".join(summary_lines)

    return final_summary, flashcards

# Set up Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Function to process notes
def process_notes(notes_content):
    prompt = f"""
You are a helpful academic assistant. Given the following academic notes, do two things:
1. Summarize the main points in bullet format.
2. Create 3-5 flashcards with clear 'Question:' and 'Answer:' labels.
Strictly follow this format:
Summary:
- Bullet 1
- Bullet 2
Flashcards:
- Question: What is...? Answer: It is...
- Question: Why does...? Answer: Because...
Here are the notes:
\"\"\"
{notes_content}
\"\"\"
"""
    response = model.generate_content(prompt)
    return response.text

# Streamlit UI
st.title("📚 Academic Notes Summarizer")
st.write("Upload your academic notes (.pdf or .docx) to get a summary and flashcards!")

uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx"])

if uploaded_file:
    with st.spinner("Processing your notes..."):
        # --- THIS LINE IS NEEDED ---
        notes_content = extract_text(uploaded_file)
        # --- / THIS LINE IS NEEDED ---

        # Now you can check the content of the variable
        if "Error" not in notes_content:
            result = process_notes(notes_content)

            st.subheader("🔍 Raw Gemini Response")
            st.code(result)

            summary, flashcards = parse_response(result) # Use the new function

            st.subheader("📝 Summary")
            if summary:
                # Use st.markdown to render bullet points correctly
                st.markdown(summary)
            else:
                st.info("No summary points extracted.")

            # --- MAKE SURE YOUR FLASHCARD DISPLAY LOGIC IS HERE ---
            st.subheader("🎓 Flashcards")
            if flashcards:
                for card in flashcards:
                    with st.expander(f"❓ {card['question']}"):
                        st.write(f"✅ **Answer:** {card['answer']}")
            else:
                st.info("No flashcards generated.")
            # --- / END OF FLASHCARD DISPLAY LOGIC ---

        else:
            # Display the error message returned by extract_text
            st.error(notes_content)

