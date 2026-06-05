# Sales Memory Agent

A deal-aware sales intelligence agent powered by Hindsight memory (retain, recall, reflect).

## Features
- Log sales interactions with prospects
- Generate AI-powered sales briefs using memory context
- Generate personalized follow-up emails
- Before vs After demo: generic AI vs memory-aware AI
- Memory Inspector to view retained memories

## Setup

### Backend
cd backend
pip3 install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

### Frontend
cd frontend
pip3 install -r requirements.txt
streamlit run app.py

### Environment Variables
Create a .env file in the backend/ folder:
HINDSIGHT_API_KEY=your_key
HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
HINDSIGHT_BANK_ID=sales-agent
