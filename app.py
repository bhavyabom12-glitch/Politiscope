from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import sqlite3
import random
import json
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'politiscope-secret-key-change-this'
application = app

# ==================== DATABASE SETUP ====================
def init_database():
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, created_at TIMESTAMP,
                  condition TEXT, theme TEXT DEFAULT 'light',
                  pre_test_data TEXT, post_test_data TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT, timestamp TIMESTAMP,
                  content_id TEXT, content_type TEXT,
                  perspective TEXT, action TEXT,
                  time_spent INTEGER, expand_duration INTEGER,
                  rating TEXT)''')
    conn.commit()
    conn.close()
    print("✅ Database initialized")

init_database()

# ==================== CONTENT DATABASE ====================
CONTENT = [
    {
        "id": "1", "type": "article", "perspective": "progressive",
        "title": "Medicare for All Explained",
        "summary": "How a single-payer system would work",
        "content": "A single-payer system would consolidate healthcare financing into one public agency. Proponents argue this reduces administrative overhead and ensures medical care as a human right regardless of income. The Congressional Budget Office estimates this would cover all Americans while eliminating premiums and deductibles.",
        "facts": ["Covers all Americans", "Eliminates premiums/deductibles", "Estimated 30M currently uninsured"],
        "source": "CBO Report 2024", "duration": 45,
        "image_url": "https://images.unsplash.com/photo-1505751172177-51ad18e739da?w=800"
    },
    {
        "id": "2", "type": "article", "perspective": "conservative",
        "title": "Market-Based Healthcare Reform",
        "summary": "Competition and choice drive quality",
        "content": "Market-based reforms focus on deregulation and increasing competition between private insurers. This approach aims to lower costs through innovation, price transparency, and personal health savings accounts. Health Savings Accounts now cover over 30 million Americans.",
        "facts": ["$450B estimated savings", "Expands Health Savings Accounts", "HSAs cover 30M+ users"],
        "source": "Heritage Foundation", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1454165833006-cc331c71dd62?w=800"
    },
    {
        "id": "3", "type": "article", "perspective": "centrist",
        "title": "The Public Option Compromise",
        "summary": "Middle ground on healthcare",
        "content": "A public option would create a government-run insurance plan that competes with private insurers, giving consumers choice while expanding coverage. This compromise aims to achieve near-universal coverage without completely displacing the private market.",
        "facts": ["$1.5T cost estimate", "88% coverage target", "Preserves private insurance option"],
        "source": "Brookings Institute", "duration": 25,
        "image_url": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=800"
    },
    {
        "id": "4", "type": "article", "perspective": "progressive",
        "title": "Green New Deal Overview",
        "summary": "Climate action and jobs",
        "content": "This resolution calls for a 10-year national mobilization to achieve 100% clean energy by 2035, create 10 million jobs, and guarantee economic security for all Americans. Includes massive investments in wind, solar, and battery storage.",
        "facts": ["$2T investment", "100% clean energy by 2035", "10M jobs created"],
        "source": "Sunrise Movement", "duration": 50,
        "image_url": "https://images.unsplash.com/photo-1466611653911-954815391f27?w=800"
    },
    {
        "id": "5", "type": "article", "perspective": "conservative",
        "title": "Energy Innovation Approach",
        "summary": "Technology over regulation",
        "content": "This approach prioritizes technological innovation over government mandates, funding research into carbon capture, advanced nuclear reactors, and next-generation solar. The strategy includes tax credits for clean energy innovation.",
        "facts": ["$500M for carbon capture", "Nuclear expansion", "R&D tax credits"],
        "source": "AEI Report", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1513828583688-c52646db42da?w=800"
    },
    {
        "id": "6", "type": "article", "perspective": "centrist",
        "title": "Climate Resilience Plan",
        "summary": "Balanced climate policy",
        "content": "This middle-ground approach pairs carbon pricing with investments in climate adaptation infrastructure. The plan would set a 2050 net-zero target while providing funding for coastal resilience and flood control.",
        "facts": ["$300B for infrastructure", "Carbon pricing included", "2050 net-zero target"],
        "source": "BPC Analysis", "duration": 35,
        "image_url": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=800"
    }
]

# ==================== HELPER FUNCTIONS ====================
def get_db():
    conn = sqlite3.connect('politiscope.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ROUTES ====================
@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/register', methods=['POST'])
def register():
    conn = get_db()
    c = conn.cursor()
    
    while True:
        user_id = str(random.randint(1000, 9999))
        c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not c.fetchone():
            break
    
    condition = random.choice(['normal', 'diverse'])
    
    c.execute('''INSERT INTO users (id, created_at, condition, theme) 
                 VALUES (?, ?, ?, 'light')''', 
              (user_id, datetime.now(), condition))
    conn.commit()
    conn.close()
    
    session['user_id'] = user_id
    session['condition'] = condition
    
    return jsonify({
        "status": "success",
        "user_id": user_id,
        "condition": condition
    })

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('user_id', '')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT id, condition, theme FROM users WHERE id = ?''', (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['condition'] = user[1]
        return jsonify({
            "status": "success",
            "user_id": user[0],
            "condition": user[1],
            "theme": user[2]
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Invalid 4-digit ID"
        })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/feed')
@login_required
def feed():
    user_id = session['user_id']
    condition = session['condition']
    
    # Generate feed based on condition
    if condition == 'normal':
        # Filter bubble - weighted toward one perspective
        # For demo, randomly choose a preferred perspective
        perspectives = ['progressive', 'centrist', 'conservative']
        fav = random.choice(perspectives)
        
        # Get items from favorite perspective (4 items)
        fav_items = [c for c in CONTENT if c['perspective'] == fav]
        if len(fav_items) < 4:
            fav_items = fav_items * (4 // len(fav_items) + 1)
        feed_items = fav_items[:4]
        
        # Add 2 items from other perspectives
        other_items = [c for c in CONTENT if c['perspective'] != fav]
        feed_items += random.sample(other_items, 2)
    else:
        # Diverse - balanced perspectives
        perspectives = ['progressive', 'centrist', 'conservative']
        feed_items = []
        for p in perspectives:
            items = [c for c in CONTENT if c['perspective'] == p]
            feed_items.extend(items[:2])  # 2 from each
    
    random.shuffle(feed_items)
    
    # Get user theme
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT theme FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    theme = user[0] if user else 'light'
    conn.close()
    
    return render_template_string(FEED_HTML, 
                                 user_id=user_id, 
                                 condition=condition,
                                 theme=theme,
                                 feed_items=feed_items)

@app.route('/api/log_interaction', methods=['POST'])
@login_required
def log_interaction():
    data = request.json
    user_id = session['user_id']
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO interactions 
                 (user_id, timestamp, content_id, content_type, perspective, action, time_spent, expand_duration, rating)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, datetime.now(), data.get('content_id'), data.get('content_type'),
               data.get('perspective'), data.get('action'), data.get('time_spent', 0),
               data.get('expand_duration'), data.get('rating')))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success"})

@app.route('/api/set_theme', methods=['POST'])
@login_required
def set_theme():
    data = request.json
    theme = data.get('theme', 'light')
    user_id = session['user_id']
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET theme = ? WHERE id = ?", (theme, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success"})

# ==================== HTML TEMPLATES ====================
HOME_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>PolitiScope Research</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 600px;
            width: 100%;
            text-align: center;
        }
        h1 { color: #333; margin-bottom: 10px; font-size: 2.5em; }
        .subtitle { color: #666; margin-bottom: 30px; }
        .btn-container { display: flex; flex-direction: column; gap: 15px; margin: 30px 0; }
        .btn {
            background: #667eea; color: white; border: none; padding: 18px;
            border-radius: 12px; font-size: 1.1em; cursor: pointer;
            transition: transform 0.2s;
        }
        .btn:hover { transform: translateY(-2px); background: #5a6fd8; }
        .btn-secondary { background: #764ba2; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 PolitiScope</h1>
        <p class="subtitle">Research Study on Political Perspectives</p>
        
        <div class="btn-container">
            <button class="btn" onclick="register()">🆕 New Participant</button>
            <button class="btn btn-secondary" onclick="login()">🔑 Returning</button>
        </div>
    </div>
    
    <script>
        async function register() {
            const res = await fetch('/register', { method: 'POST' });
            const data = await res.json();
            alert(`✅ Your 4-digit ID: ${data.user_id}\\n\\n⚠️ SAVE THIS! You'll need it to log in.`);
            window.location.href = '/feed';
        }
        
        async function login() {
            const id = prompt("Enter your 4-digit ID:");
            if (id && id.length === 4 && /^\\d+$/.test(id)) {
                const res = await fetch('/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: id})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    window.location.href = '/feed';
                } else {
                    alert(data.message);
                }
            } else {
                alert("Please enter a valid 4-digit ID");
            }
        }
    </script>
</body>
</html>
'''

FEED_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>PolitiScope Feed</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: {{ '#000' if theme == 'dark' else '#f5f5f5' }};
            color: {{ '#fff' if theme == 'dark' else '#333' }};
            padding: 20px;
            transition: all 0.3s;
        }
        .header {
            position: sticky;
            top: 0;
            z-index: 100;
            background: {{ '#000' if theme == 'dark' else '#f5f5f5' }};
            padding: 15px 0;
            margin-bottom: 20px;
            border-bottom: 1px solid {{ '#333' if theme == 'dark' else '#ddd' }};
        }
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 600px;
            margin: 0 auto;
        }
        .user-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .user-id {
            font-family: monospace;
            background: {{ '#333' if theme == 'dark' else '#f0f0f0' }};
            padding: 8px 15px;
            border-radius: 20px;
        }
        .timer-container {
            text-align: center;
            background: {{ '#1a1a1a' if theme == 'dark' else 'white' }};
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px {{ 'rgba(0,0,0,0.3)' if theme == 'dark' else 'rgba(0,0,0,0.1)' }};
        }
        .timer-display {
            font-size: 3em;
            font-family: monospace;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        .timer-label {
            font-size: 0.9em;
            color: #888;
            margin-bottom: 5px;
        }
        .target-time {
            font-size: 0.9em;
            color: #888;
            margin-top: 5px;
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: {{ '#333' if theme == 'dark' else '#e0e0e0' }};
            border-radius: 4px;
            margin: 15px 0;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #ff6b6b, #4ecdc4, #45b7d1);
            width: 0%;
            transition: width 0.3s;
        }
        .feed-container {
            max-width: 600px;
            margin: 0 auto;
        }
        .content-card {
            background: {{ '#1a1a1a' if theme == 'dark' else 'white' }};
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px {{ 'rgba(0,0,0,0.3)' if theme == 'dark' else 'rgba(0,0,0,0.1)' }};
            border-left: 6px solid;
        }
        .progressive { border-left-color: #ff6b6b; }
        .centrist { border-left-color: #4ecdc4; }
        .conservative { border-left-color: #45b7d1; }
        .badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 15px;
        }
        .badge-progressive { background: #ff6b6b20; color: #ff6b6b; }
        .badge-centrist { background: #4ecdc420; color: #4ecdc4; }
        .badge-conservative { background: #45b7d120; color: #45b7d1; }
        h2 { font-size: 1.5em; margin-bottom: 10px; }
        .summary {
            font-size: 1em;
            color: {{ '#ccc' if theme == 'dark' else '#666' }};
            margin-bottom: 15px;
            line-height: 1.5;
        }
        img {
            width: 100%;
            height: 200px;
            object-fit: cover;
            border-radius: 10px;
            margin: 15px 0;
        }
        .expand-btn {
            background: {{ 'rgba(255,255,255,0.05)' if theme == 'dark' else 'rgba(0,0,0,0.02)' }};
            border: 1px solid {{ '#444' if theme == 'dark' else '#ddd' }};
            color: {{ '#fff' if theme == 'dark' else '#333' }};
            padding: 12px;
            border-radius: 25px;
            cursor: pointer;
            width: 100%;
            margin: 10px 0;
            font-size: 14px;
            text-align: left;
            transition: background 0.2s;
        }
        .expand-btn:hover {
            background: {{ 'rgba(255,255,255,0.1)' if theme == 'dark' else 'rgba(0,0,0,0.05)' }};
        }
        .expanded-content {
            display: none;
            margin-top: 15px;
            padding: 20px;
            background: {{ 'rgba(255,255,255,0.02)' if theme == 'dark' else 'rgba(0,0,0,0.02)' }};
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        .facts {
            background: {{ 'rgba(102,126,234,0.1)' if theme == 'dark' else 'rgba(102,126,234,0.05)' }};
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }
        .facts ul {
            margin-top: 10px;
            padding-left: 20px;
        }
        .facts li {
            margin-bottom: 5px;
        }
        .source {
            color: #888;
            font-size: 14px;
            margin-top: 10px;
        }
        .buttons {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .btn {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-weight: bold;
            color: white;
            transition: transform 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
        .btn-interested { background: #3498db; }
        .btn-interested.active { background: #2ecc71; }
        .btn-informative { background: #2ecc71; }
        .btn-not-useful { background: #e74c3c; }
        .theme-toggle {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: {{ '#333' if theme == 'dark' else '#f0f0f0' }};
            color: {{ '#fff' if theme == 'dark' else '#333' }};
            border: none;
            padding: 12px 25px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 14px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
        }
        .exit-btn {
            position: fixed;
            top: 20px;
            right: 20px;
            background: {{ '#e74c3c' if theme == 'dark' else '#f0f0f0' }};
            color: {{ '#fff' if theme == 'dark' else '#333' }};
            border: none;
            padding: 8px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            z-index: 1000;
        }
        .exit-btn:hover {
            background: #c0392b;
            color: white;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="user-info">
                <span class="user-id">{{ user_id }}</span>
            </div>
            <div class="timer" id="timer">00:00</div>
        </div>
    </div>
    
    <!-- PROMINENT 20-MINUTE TIMER DISPLAY -->
    <div class="timer-container">
        <div class="timer-label">⏱️ TODAY'S SESSION</div>
        <div class="timer-display" id="bigTimer">00:00</div>
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        <div class="target-time">Target: 20 minutes • You can stay longer or leave anytime</div>
    </div>
    
    <div class="feed-container" id="feed"></div>
    
    <button class="theme-toggle" onclick="toggleTheme()">
        {{ '☀️ Light' if theme == 'dark' else '🌙 Dark' }}
    </button>
    
    <button class="exit-btn" onclick="exitSession()">✕ Exit</button>
    
    <script>
        const userId = '{{ user_id }}';
        const condition = '{{ condition }}';
        const feedItems = {{ feed_items | tojson }};
        
        let startTime = Date.now();
        let expandTimes = {};
        let cardStartTimes = {};
        let currentInteractions = [];
        
        console.log('🔬 Research condition for user', userId + ':', condition);
        console.log('Feed loaded with', feedItems.length, 'items');
        
        // Render feed
        function renderFeed() {
            const feed = document.getElementById('feed');
            if (!feed) return;
            
            feed.innerHTML = '';
            
            if (!feedItems || feedItems.length === 0) {
                feed.innerHTML = '<div style="text-align: center; padding: 40px;">No content available</div>';
                return;
            }
            
            feedItems.forEach((item, index) => {
                const card = createCard(item, index);
                feed.appendChild(card);
            });
            
            // Start timer for first card
            if (feedItems.length > 0) {
                cardStartTimes[0] = Date.now();
            }
        }
        
        function createCard(item, index) {
            const card = document.createElement('div');
            card.className = `content-card ${item.perspective}`;
            card.dataset.contentId = item.id;
            card.dataset.index = index;
            
            const typeEmoji = item.type === 'video' ? '🎬' : '📰';
            const perspectiveEmoji = item.perspective === 'progressive' ? '🔴' : 
                                    item.perspective === 'centrist' ? '⚪' : '🔵';
            
            card.innerHTML = `
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <span class="badge badge-${item.perspective}">
                            ${perspectiveEmoji} ${item.perspective.toUpperCase()}
                        </span>
                        <span style="font-size: 12px; color: #888;">${typeEmoji} ${item.type}</span>
                    </div>
                    
                    <h2>${item.title}</h2>
                    <div class="summary">${item.summary}</div>
                    
                    <img src="${item.image_url}" alt="Content" onerror="this.src='https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800'">
                    
                    <button class="expand-btn" onclick="toggleExpand(this, '${item.id}', '${item.type}', '${item.perspective}')">
                        ▼ Read Full Analysis
                    </button>
                    
                    <div class="expanded-content" id="expand-${item.id}">
                        <div style="line-height: 1.6;">${item.content}</div>
                        <div class="facts">
                            <strong>📌 Key Facts:</strong>
                            <ul>
                                ${item.facts.map(f => `<li>${f}</li>`).join('')}
                            </ul>
                        </div>
                        <div class="source">Source: ${item.source}</div>
                    </div>
                </div>
                
                <div>
                    <div class="buttons">
                        <button class="btn btn-interested" onclick="markInterested('${item.id}', '${item.type}', '${item.perspective}', this)">
                            🔖 Interested
                        </button>
                        <button class="btn btn-informative" onclick="rateContent('${item.id}', 'informative', '${item.type}', '${item.perspective}')">
                            ✅ Informative
                        </button>
                        <button class="btn btn-not-useful" onclick="rateContent('${item.id}', 'not_useful', '${item.type}', '${item.perspective}')">
                            ❌ Not Useful
                        </button>
                    </div>
                </div>
            `;
            
            return card;
        }
        
        // Expand/collapse tracking
        function toggleExpand(btn, contentId, type, perspective) {
            const expanded = document.getElementById(`expand-${contentId}`);
            const isExpanding = expanded.style.display === 'none';
            
            if (isExpanding) {
                expanded.style.display = 'block';
                btn.innerHTML = '▲ Collapse Analysis';
                expandTimes[contentId] = Date.now();
                
                fetch('/api/log_interaction', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        content_id: contentId,
                        content_type: type,
                        perspective: perspective,
                        action: 'expand_start'
                    })
                });
            } else {
                expanded.style.display = 'none';
                btn.innerHTML = '▼ Read Full Analysis';
                
                if (expandTimes[contentId]) {
                    const duration = Math.floor((Date.now() - expandTimes[contentId]) / 1000);
                    
                    fetch('/api/log_interaction', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            content_id: contentId,
                            content_type: type,
                            perspective: perspective,
                            action: 'expand_end',
                            expand_duration: duration
                        })
                    });
                    
                    delete expandTimes[contentId];
                }
            }
        }
        
        // Interested button
        function markInterested(contentId, type, perspective, btn) {
            btn.classList.add('active');
            btn.textContent = '✓ Interested';
            
            fetch('/api/log_interaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content_id: contentId,
                    content_type: type,
                    perspective: perspective,
                    action: 'interested'
                })
            });
            
            alert('✅ Thanks! Your interest has been recorded.');
        }
        
        // Rate content
        function rateContent(contentId, rating, type, perspective) {
            fetch('/api/log_interaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content_id: contentId,
                    content_type: type,
                    perspective: perspective,
                    action: 'rate',
                    rating: rating
                })
            });
            
            alert(rating === 'informative' ? '✅ Rated as informative' : '❌ Rated as not useful');
        }
        
        // Timer and progress - UPDATED with big display
        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            const timeString = `${mins.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}`;
            
            // Update both timers
            document.getElementById('timer').textContent = timeString;
            document.getElementById('bigTimer').textContent = timeString;
            
            // Progress toward 20 minutes (1200 seconds)
            const progress = Math.min((elapsed / 1200) * 100, 100);
            document.getElementById('progressFill').style.width = progress + '%';
        }
        
        // Exit session - NO forced completion after 6 items
        function exitSession() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            
            if (confirm(`⏱️ You spent ${mins}:${secs.toString().padStart(2,'0')} minutes today.\n\nExit to homepage?`)) {
                window.location.href = '/';
            }
        }
        
        // Toggle theme
        async function toggleTheme() {
            const isDark = document.body.style.background === 'rgb(0, 0, 0)';
            const theme = isDark ? 'light' : 'dark';
            
            await fetch('/api/set_theme', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({theme: theme})
            });
            
            location.reload();
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            renderFeed();
            setInterval(updateTimer, 1000);
        });
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
