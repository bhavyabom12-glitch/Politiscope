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

init_database()

# ==================== CONTENT (SIMPLIFIED) ====================
CONTENT = [
    {
        "id": "1", "type": "article", "perspective": "progressive",
        "title": "Medicare for All", "summary": "Universal healthcare",
        "content": "A single-payer system would cover all Americans.",
        "facts": ["Covers 30M uninsured", "Eliminates premiums"],
        "source": "CBO", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1505751172177-51ad18e739da?w=800"
    },
    {
        "id": "2", "type": "article", "perspective": "conservative",
        "title": "Market Reform", "summary": "Competition & choice",
        "content": "Market competition drives down costs.",
        "facts": ["HSAs cover 30M", "$450B savings"],
        "source": "Heritage", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1454165833006-cc331c71dd62?w=800"
    },
    {
        "id": "3", "type": "article", "perspective": "centrist",
        "title": "Public Option", "summary": "Middle ground",
        "content": "Government option competes with private insurers.",
        "facts": ["88% coverage", "$1.5T cost"],
        "source": "Brookings", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=800"
    },
    {
        "id": "4", "type": "article", "perspective": "progressive",
        "title": "Green New Deal", "summary": "Climate action",
        "content": "100% clean energy by 2035.",
        "facts": ["$2T investment", "10M jobs"],
        "source": "Sunrise", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1466611653911-954815391f27?w=800"
    },
    {
        "id": "5", "type": "article", "perspective": "conservative",
        "title": "Energy Innovation", "summary": "Tech solutions",
        "content": "Carbon capture and nuclear power.",
        "facts": ["$500M R&D", "Nuclear expansion"],
        "source": "AEI", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1513828583688-c52646db42da?w=800"
    },
    {
        "id": "6", "type": "article", "perspective": "centrist",
        "title": "Climate Resilience", "summary": "Adaptation",
        "content": "Carbon pricing + infrastructure.",
        "facts": ["$300B investment", "2050 net-zero"],
        "source": "BPC", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=800"
    }
]

# ==================== ROUTES ====================
@app.route('/')
def home():
    return HOME_HTML

@app.route('/register', methods=['POST'])
def register():
    while True:
        user_id = str(random.randint(1000, 9999))
        conn = sqlite3.connect('politiscope.db')
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not c.fetchone():
            break
        conn.close()
    
    condition = random.choice(['normal', 'diverse'])
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    c.execute("INSERT INTO users (id, created_at, condition, theme) VALUES (?, ?, ?, 'light')",
              (user_id, datetime.now(), condition))
    conn.commit()
    conn.close()
    
    session['user_id'] = user_id
    session['condition'] = condition
    return jsonify({"status": "success", "user_id": user_id, "condition": condition})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('user_id', '')
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    c.execute("SELECT id, condition, theme FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['condition'] = user[1]
        return jsonify({"status": "success", "user_id": user[0], "condition": user[1], "theme": user[2]})
    return jsonify({"status": "error", "message": "Invalid ID"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/feed')
def feed():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    user_id = session['user_id']
    condition = session['condition']
    
    # Generate feed based on condition
    feed_items = []
    if condition == 'normal':
        # Filter bubble - show similar perspectives
        perspectives = [c['perspective'] for c in CONTENT]
        fav = random.choice(perspectives)  # Simplified - in real app, track user preferences
        items = [c for c in CONTENT if c['perspective'] == fav][:4]
        items += random.sample([c for c in CONTENT if c['perspective'] != fav], 2)
        feed_items = items
    else:
        # Diverse - balanced
        items_by_perspective = {
            'progressive': [c for c in CONTENT if c['perspective'] == 'progressive'][0],
            'centrist': [c for c in CONTENT if c['perspective'] == 'centrist'][0],
            'conservative': [c for c in CONTENT if c['perspective'] == 'conservative'][0]
        }
        feed_items = list(items_by_perspective.values()) * 2
    
    random.shuffle(feed_items)
    
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    c.execute("SELECT theme FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    theme = user[0] if user else 'light'
    conn.close()
    
    return render_template_string(FEED_HTML, user_id=user_id, condition=condition, 
                                 theme=theme, feed_items=json.dumps(feed_items))

@app.route('/api/log_interaction', methods=['POST'])
def log_interaction():
    if 'user_id' not in session:
        return jsonify({"status": "error"})
    
    data = request.json
    user_id = session['user_id']
    
    conn = sqlite3.connect('politiscope.db')
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
def set_theme():
    if 'user_id' not in session:
        return jsonify({"status": "error"})
    
    data = request.json
    theme = data.get('theme', 'light')
    user_id = session['user_id']
    
    conn = sqlite3.connect('politiscope.db')
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
        <p style="color: #666; margin-bottom: 30px;">Filter Bubble Research Study</p>
        
        <div class="btn-container">
            <button class="btn" onclick="register()">🆕 New Participant</button>
            <button class="btn btn-secondary" onclick="login()">🔑 Returning</button>
        </div>
    </div>
    
    <script>
        async function register() {
            const res = await fetch('/register', { method: 'POST' });
            const data = await res.json();
            alert(`✅ Your ID: ${data.user_id}\\n\\n⚠️ SAVE THIS!`);
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
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid {{ '#333' if theme == 'dark' else '#ddd' }};
        }
        .user-id {
            font-family: monospace;
            background: {{ '#333' if theme == 'dark' else '#f0f0f0' }};
            padding: 8px 15px;
            border-radius: 20px;
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
        h2 { margin-bottom: 10px; }
        img {
            width: 100%;
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
        }
        .expanded {
            display: none;
            margin-top: 15px;
            padding: 20px;
            background: {{ 'rgba(255,255,255,0.02)' if theme == 'dark' else 'rgba(0,0,0,0.02)' }};
            border-radius: 10px;
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
        }
    </style>
</head>
<body>
    <div class="header">
        <div>ID: <span class="user-id">{{ user_id }}</span></div>
        <div>Condition: {{ condition }}</div>
        <div id="timer">00:00</div>
    </div>
    
    <div class="feed-container" id="feed"></div>
    
    <button class="theme-toggle" onclick="toggleTheme()">
        {{ '☀️ Light' if theme == 'dark' else '🌙 Dark' }}
    </button>
    
    <script>
        const userId = '{{ user_id }}';
        const feedItems = {{ feed_items | safe }};
        let startTime = Date.now();
        let expandTimes = {};
        
        function renderFeed() {
            const feed = document.getElementById('feed');
            feed.innerHTML = '';
            
            feedItems.forEach((item, i) => {
                const card = document.createElement('div');
                card.className = `content-card ${item.perspective}`;
                card.innerHTML = `
                    <span class="badge badge-${item.perspective}">${item.perspective.toUpperCase()}</span>
                    <h2>${item.title}</h2>
                    <p style="color: ${theme === 'dark' ? '#ccc' : '#555'}">${item.summary}</p>
                    <img src="${item.image_url}" alt="Content">
                    
                    <button class="expand-btn" onclick="toggleExpand(this, '${item.id}')">
                        ▼ Read More
                    </button>
                    <div class="expanded" id="expand-${item.id}">
                        <p style="line-height: 1.6;">${item.content}</p>
                        <div style="margin-top: 15px;">
                            <strong>Key Facts:</strong>
                            <ul style="margin-top: 10px; padding-left: 20px;">
                                ${item.facts.map(f => `<li>${f}</li>`).join('')}
                            </ul>
                        </div>
                        <div style="margin-top: 15px; color: #888;">Source: ${item.source}</div>
                    </div>
                    
                    <div class="buttons">
                        <button class="btn btn-interested" onclick="markInterested('${item.id}', this)">🔖 Interested</button>
                        <button class="btn btn-informative" onclick="rate('${item.id}', 'informative')">✅ Informative</button>
                        <button class="btn btn-not-useful" onclick="rate('${item.id}', 'not_useful')">❌ Not Useful</button>
                    </div>
                `;
                feed.appendChild(card);
            });
        }
        
        function toggleExpand(btn, id) {
            const expanded = document.getElementById(`expand-${id}`);
            if (expanded.style.display === 'none') {
                expanded.style.display = 'block';
                btn.innerHTML = '▲ Show Less';
                expandTimes[id] = Date.now();
            } else {
                expanded.style.display = 'none';
                btn.innerHTML = '▼ Read More';
                
                if (expandTimes[id]) {
                    const duration = Math.floor((Date.now() - expandTimes[id]) / 1000);
                    fetch('/api/log_interaction', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            content_id: id,
                            action: 'expand',
                            expand_duration: duration
                        })
                    });
                    delete expandTimes[id];
                }
            }
        }
        
        function markInterested(id, btn) {
            btn.classList.add('active');
            btn.textContent = '✓ Interested';
            
            fetch('/api/log_interaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content_id: id,
                    action: 'interested'
                })
            });
        }
        
        function rate(id, rating) {
            fetch('/api/log_interaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content_id: id,
                    action: 'rate',
                    rating: rating
                })
            });
            alert(rating === 'informative' ? '✅ Thanks!' : '❌ Noted');
        }
        
        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            document.getElementById('timer').textContent = `${mins.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}`;
        }
        
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
        
        renderFeed();
        setInterval(updateTimer, 1000);
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)