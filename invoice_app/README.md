# Invoice Parser Web App

This Flask application allows you to upload a PDF or image (PNG, JPG) invoice and returns parsed data using the OpenAI GPT API. The app extracts text from the uploaded file, sends it to OpenAI for parsing and displays the suggested accounting entries based on `predkontace.json`.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file or export the API key in your environment:

```
OPENAI_API_KEY=your_openai_key_here
```

3. Run the application:

```bash
python invoice_app/app.py
```

Then open `http://localhost:5000` in your browser.
