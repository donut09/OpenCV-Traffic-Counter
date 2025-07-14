import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
import openai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret!')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

PREDKONTACE_PATH = os.path.join(os.path.dirname(__file__), 'predkontace.json')
with open(PREDKONTACE_PATH, 'r', encoding='utf-8') as f:
    PREDKONTACE = json.load(f)

openai.api_key = os.getenv('OPENAI_API_KEY')

SYSTEM_PROMPT = (
    "Jsi účetní asistent. Z poskytnutého textu dokladu extrahuj následující pole"
    ": ico, date, base, vat, currency. Vrať čisté JSON bez vysvětlení ve tvaru "
    "{\"ico\":..., \"date\":..., \"base\":..., \"vat\":..., \"currency\":..., \"raw_text\":...}"
)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(file_storage) -> str:
    filename = file_storage.filename
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        reader = PdfReader(file_storage)
        text = "\n".join(page.extract_text() or '' for page in reader.pages)
    else:
        image = Image.open(file_storage)
        text = pytesseract.image_to_string(image, lang='ces+eng')
    return text


def parse_amount(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).replace(' ', '').replace(',', '.')
    try:
        return float(value)
    except ValueError:
        return None


def call_openai(text: str) -> dict:
    if not openai.api_key:
        raise RuntimeError('OpenAI API key not configured')
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': text}
        ],
        temperature=0
    )
    content = response['choices'][0]['message']['content']
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError('Invalid response from OpenAI')
    return data


def build_accounting_suggestions(data: dict) -> list:
    suggestions = []
    base = parse_amount(data.get('base'))
    vat = parse_amount(data.get('vat'))
    if base is not None:
        cfg = PREDKONTACE.get('zaklad')
        suggestions.append({
            'account': cfg['account'],
            'debit': base,
            'credit': 0.0,
            'description': cfg['description']
        })
    if vat is not None:
        cfg = PREDKONTACE.get('dph')
        suggestions.append({
            'account': cfg['account'],
            'debit': vat,
            'credit': 0.0,
            'description': cfg['description']
        })
    if base is not None or vat is not None:
        total = (base or 0) + (vat or 0)
        cfg = PREDKONTACE.get('payment')
        suggestions.append({
            'account': cfg['account'],
            'debit': 0.0,
            'credit': total,
            'description': cfg['description']
        })
    return suggestions


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash('Unsupported file type')
            return redirect(request.url)
        try:
            text = extract_text(file)
            gpt_data = call_openai(text)
            gpt_data['raw_text'] = text
            gpt_data['accounting_suggestions'] = build_accounting_suggestions(gpt_data)
            return render_template('result.html', data=gpt_data)
        except Exception as e:
            flash(str(e))
            return redirect(request.url)
    return render_template('upload.html')


if __name__ == '__main__':
    app.run(debug=True)
