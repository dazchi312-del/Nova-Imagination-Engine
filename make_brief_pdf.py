from fpdf import FPDF
import os

class NovaBriefPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'PROJECT NOVA: NOE EDUCATIONAL BRIEF', 0, 1, 'C')
        self.ln(10)

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, label, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, text):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 6, text)
        self.ln()

pdf = NovaBriefPDF()
pdf.add_page()

sections = [
    ("Executive Summary", "Nova is a self-improving AI output system utilizing a secondary AI to judge and refine outputs. It creates a deterministic feedback loop for quality control."),
    ("The Architecture", "Primary Node: Lenovo Legion Pro 7i (Nemotron 70B)\nValidation Node: MacBook Pro M4 (Llama 3.1 8B)\nRole: The Reflector model evaluates the primary node's generation."),
    ("Scoring Matrix", "1. Quality (30%)\n2. Clarity (25%)\n3. Structure (20%)\n4. Hallucination Risk (15%)\n5. Identity Alignment (10%)")
]

for title, body in sections:
    pdf.chapter_title(title)
    pdf.chapter_body(body)

# Change this to your preferred output location
output_path = "Nova_Output_Engine_Brief.pdf"
pdf.output(output_path)
print(f'Success: {output_path} generated.')
