from flask import Flask, request, jsonify
import os
import requests
import re

app = Flask(__name__)

ASI_API_KEY = os.getenv("ASI_ONE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_FACT_CHECK_API_KEY")

ASI_ONE_URL = "https://api.asi1.ai/v1/chat/completions"
GOOGLE_FACT_CHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

def search_google_fact_check(query):
    if not GOOGLE_API_KEY:
        return None
    try:
        params = {
            "query": query[:100],
            "key": GOOGLE_API_KEY,
            "languageCode": "en"
        }
        response = requests.get(GOOGLE_FACT_CHECK_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if "claims" in data and len(data["claims"]) > 0:
            claim = data["claims"][0]
            if "claimReview" in claim and len(claim["claimReview"]) > 0:
                review = claim["claimReview"][0]
                return review.get('textualRating', 'N/A')
        return None
    except:
        return None

def fetch_url_content(url):
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        content = response.text[:2000]
        
        trusted_domains = ["bbc.com", "reuters.com", "ap.org", "apnews.com", "theguardian.com", "nytimes.com", "bbc.co.uk"]
        is_trusted = any(domain in url.lower() for domain in trusted_domains)
        
        return content, is_trusted
    except:
        return None, False

def analyze_trust(text):
    if not text or not text.strip():
        return {"success": False, "score": None, "reason": "Empty input"}
    
    is_trusted_source = False
    analyze_text = text
    
    if text.startswith("http://") or text.startswith("https://"):
        result = fetch_url_content(text)
        if result[0] is None:
            return {"success": False, "score": None, "reason": "Could not fetch URL"}
        analyze_text = result[0][:1000]
        is_trusted_source = result[1]
    
    google_result = search_google_fact_check(text[:50])
    
    payload = {
        "model": "asi1-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a trustworthiness analyzer. Respond in this exact format:\nSCORE: [0-100 number]\nCATEGORY: [legitimate/clickbait/fake news/AI-generated/biased]\nREASON: [one sentence]"
            },
            {
                "role": "user",
                "content": f"Rate trustworthiness of this text:\n\n{analyze_text}"
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ASI_API_KEY}"
    }

    try:
        response = requests.post(ASI_ONE_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            result = data["choices"][0]["message"]["content"]
            score = extract_score(result)
            category = extract_category(result)
            reason = extract_reason(result)
            
            if text.startswith("http") and not is_trusted_source and score and score > 50:
                score = max(score - 20, 0)
            
            return {
                "success": True,
                "score": score,
                "category": category,
                "reason": reason,
                "google_check": google_result,
                "is_trusted_source": is_trusted_source
            }
        else:
            return {"success": False, "score": None, "reason": "API error"}
            
    except Exception as e:
        return {"success": False, "score": None, "reason": str(e)}

def extract_score(text):
    match = re.search(r'SCORE:\s*(\d{1,3})', text, re.IGNORECASE)
    if match:
        score = int(match.group(1))
        if 0 <= score <= 100:
            return score
    return 50  # Default if not found

def extract_category(text):
    match = re.search(r'CATEGORY:\s*(\w+(?:\s+\w+)*)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Unknown"

def extract_reason(text):
    match = re.search(r'REASON:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:300]
    return "Analysis complete"

@app.route('/')
def index():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trust Checker</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 600px;
            width: 100%;
            padding: 40px;
        }

        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }

        .subtitle {
            color: #999;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .warning {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin-bottom: 25px;
            border-radius: 4px;
            font-size: 13px;
            color: #856404;
        }

        .input-group {
            margin-bottom: 20px;
        }

        label {
            display: block;
            color: #333;
            margin-bottom: 8px;
            font-weight: 600;
            font-size: 14px;
        }

        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }

        input:focus {
            outline: none;
            border-color: #667eea;
        }

        button {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }

        button:hover {
            transform: translateY(-2px);
        }

        button:active {
            transform: translateY(0);
        }

        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        .loading {
            text-align: center;
            padding: 20px;
            color: #667eea;
            display: none;
        }

        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .results {
            display: none;
            margin-top: 30px;
            padding-top: 30px;
            border-top: 2px solid #eee;
        }

        .gauge {
            text-align: center;
            margin-bottom: 30px;
        }

        .gauge-circle {
            width: 200px;
            height: 200px;
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            font-weight: bold;
            color: white;
            position: relative;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }

        .score-label {
            font-size: 14px;
            color: #999;
            margin-bottom: 8px;
        }

        .category-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 15px;
        }

        .category-fake {
            background: #ff6b6b;
            color: white;
        }

        .category-clickbait {
            background: #ffa94d;
            color: white;
        }

        .category-ai {
            background: #74c0fc;
            color: white;
        }

        .category-biased {
            background: #ffd43b;
            color: #333;
        }

        .category-legitimate {
            background: #51cf66;
            color: white;
        }

        .reason {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            color: #333;
            font-size: 14px;
            line-height: 1.6;
        }

        .details {
            font-size: 13px;
            color: #666;
            line-height: 1.6;
        }

        .detail-item {
            margin-bottom: 10px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 6px;
        }

        .detail-label {
            font-weight: 600;
            color: #333;
        }

        .error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            padding: 12px;
            border-radius: 6px;
            margin-top: 15px;
        }

        .trusted-source {
            color: #51cf66;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Trust Checker</h1>
        <p class="subtitle">Analyze text & URLs for trustworthiness</p>
        
        <div class="warning">
            ⚠️ AI knowledge ends January 2025 • Results are preliminary analysis only
        </div>

        <div class="input-group">
            <label for="textInput">Enter text or URL:</label>
            <input type="text" id="textInput" placeholder="Paste text or URL here..." />
        </div>

        <button id="analyzeBtn" onclick="analyze()">Analyze</button>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Analyzing...</p>
        </div>

        <div class="results" id="results">
            <div class="gauge">
                <div class="score-label">Trustworthiness Score</div>
                <div class="gauge-circle" id="gaugeCircle">0</div>
            </div>

            <div style="text-align: center; margin-bottom: 25px;">
                <div class="category-badge" id="categoryBadge">Unknown</div>
            </div>

            <div class="reason" id="reason"></div>

            <div class="details" id="details"></div>

            <div class="error" id="error" style="display: none;"></div>
        </div>
    </div>

    <script>
        async function analyze() {
            const text = document.getElementById('textInput').value.trim();
            
            if (!text) {
                alert('Please enter text or URL');
                return;
            }

            const btn = document.getElementById('analyzeBtn');
            const loading = document.getElementById('loading');
            const results = document.getElementById('results');
            const error = document.getElementById('error');

            btn.disabled = true;
            loading.style.display = 'block';
            results.style.display = 'none';
            error.style.display = 'none';

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });

                const data = await response.json();

                if (data.success) {
                    displayResults(data);
                    results.style.display = 'block';
                } else {
                    error.textContent = data.error || data.reason || 'Analysis failed';
                    error.style.display = 'block';
                    results.style.display = 'block';
                }
            } catch (err) {
                error.textContent = 'Error: ' + err.message;
                error.style.display = 'block';
                results.style.display = 'block';
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
            }
        }

        function displayResults(data) {
            const score = data.score || 0;
            const category = data.category || 'Unknown';
            
            const gaugeCircle = document.getElementById('gaugeCircle');
            gaugeCircle.textContent = score;
            
            let bgColor;
            if (score >= 70) bgColor = '#51cf66';
            else if (score >= 50) bgColor = '#ffa94d';
            else bgColor = '#ff6b6b';
            
            gaugeCircle.style.background = bgColor;

            const categoryBadge = document.getElementById('categoryBadge');
            const categoryClass = 'category-' + category.toLowerCase().replace(' ', '');
            categoryBadge.textContent = category.toUpperCase();
            categoryBadge.className = 'category-badge ' + categoryClass;

            document.getElementById('reason').textContent = data.reason || 'No analysis available';

            let detailsHtml = '';
            if (data.is_trusted_source) {
                detailsHtml += '<div class="detail-item"><span class="detail-label trusted-source">✓ From trusted news source</span></div>';
            }
            if (data.google_check) {
                detailsHtml += `<div class="detail-item"><span class="detail-label">Fact Check:</span> ${data.google_check}</div>`;
            }
            detailsHtml += '<div class="detail-item" style="font-size: 12px; color: #999;">AI knowledge: January 2025</div>';
            
            document.getElementById('details').innerHTML = detailsHtml;
        }

        document.getElementById('textInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') analyze();
        });
    </script>
</body>
</html>"""
    return html

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.json
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({"success": False, "error": "Empty input"}), 400
    
    # Try to use UAgent if available, fallback to direct analysis
    try:
        # For now, use direct analysis
        # In production, you would send to UAgent endpoint
        result = analyze_trust(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)