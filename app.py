import os
import random
import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from functools import wraps
import time

# LangChain imports
from langchain_community.document_loaders import RSSFeedLoader

app = Flask(__name__)
app.secret_key = 'politiscope-secret-key-change-this'
application = app

# ==================== RSS FEEDS CONFIGURATION ====================
# Organized by political perspective
RSS_FEEDS = {
    'progressive': [
        {
            'name': 'NPR News',
            'feed_url': 'https://feeds.npr.org/1001/rss.xml',
            'website': 'https://npr.org',
            'category': 'general'
        },
        {
            'name': 'The Guardian US',
            'feed_url': 'https://www.theguardian.com/world/usa/rss',
            'website': 'https://theguardian.com/us',
            'category': 'general'
        },
        {
            'name': 'Mother Jones',
            'feed_url': 'https://www.motherjones.com/feed/',
            'website': 'https://motherjones.com',
            'category': 'politics'
        },
        {
            'name': 'Vox',
            'feed_url': 'https://www.vox.com/rss/index.xml',
            'website': 'https://vox.com',
            'category': 'politics'
        }
    ],
    'conservative': [
        {
            'name': 'Fox News Politics',
            'feed_url': 'https://moxie.foxnews.com/feedburner/politics.xml',
            'website': 'https://foxnews.com/politics',
            'category': 'politics'
        },
        {
            'name': 'National Review',
            'feed_url': 'https://www.nationalreview.com/feed/',
            'website': 'https://nationalreview.com',
            'category': 'politics'
        },
        {
            'name': 'Washington Times',
            'feed_url': 'https://www.washingtontimes.com/rss/headlines/',
            'website': 'https://washingtontimes.com',
            'category': 'general'
        },
        {
            'name': 'Daily Wire',
            'feed_url': 'https://www.dailywire.com/feeds/rss.xml',
            'website': 'https://dailywire.com',
            'category': 'politics'
        }
    ],
    'centrist': [
        {
            'name': 'Reuters Politics',
            'feed_url': 'https://feeds.reuters.com/news/politics',
            'website': 'https://reuters.com/politics',
            'category': 'general'
        },
        {
            'name': 'AP Top News',
            'feed_url': 'https://feeds.ap.org/feeds/feed/APTopNews',
            'website': 'https://apnews.com',
            'category': 'general'
        },
        {
            'name': 'The Hill',
            'feed_url': 'https://thehill.com/feed/',
            'website': 'https://thehill.com',
            'category': 'politics'
        },
        {
            'name': 'BBC News US & Canada',
            'feed_url': 'http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml',
            'website': 'https://bbc.com/news',
            'category': 'general'
        }
    ]
}

# ==================== DATABASE SETUP ====================
def init_database():
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, created_at TIMESTAMP,
                  condition TEXT, theme TEXT DEFAULT 'light',
                  pre_test_data TEXT, post_test_data TEXT)''')
    
    # Articles table (simplified - LangChain gives us rich metadata)
    c.execute('''CREATE TABLE IF NOT EXISTS articles
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guid TEXT UNIQUE,
                  title TEXT,
                  summary TEXT,
                  content TEXT,
                  link TEXT,
                  image_url TEXT,
                  source_name TEXT,
                  source_url TEXT,
                  perspective TEXT,
                  keywords TEXT,
                  published TIMESTAMP,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Interactions table
    c.execute('''CREATE TABLE IF NOT EXISTS interactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  article_id INTEGER,
                  timestamp TIMESTAMP,
                  action TEXT,
                  time_spent INTEGER,
                  expand_duration INTEGER,
                  rating TEXT,
                  FOREIGN KEY (article_id) REFERENCES articles(id))''')
    
    # Indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_articles_perspective ON articles(perspective)')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

init_database()

# ==================== LANGCHAIN RSS FETCHER ====================
def fetch_with_langchain(max_articles_per_feed=5):
    """Use LangChain's RSSFeedLoader to fetch and parse articles"""
    
    # Collect all feed URLs
    all_urls = []
    source_map = {}  # Map URL to source info
    
    for perspective, feeds in RSS_FEEDS.items():
        for feed in feeds:
            all_urls.append(feed['feed_url'])
            source_map[feed['feed_url']] = {
                'name': feed['name'],
                'website': feed['website'],
                'perspective': perspective,
                'category': feed['category']
            }
    
    print(f"📡 Fetching {len(all_urls)} RSS feeds with LangChain...")
    
    try:
        # Initialize LangChain loader with NLP enabled for better content
        loader = RSSFeedLoader(
            urls=all_urls,
            nlp=True  # Enables keyword extraction, summarization
        )
        
        # Load all documents
        documents = loader.load()
        print(f"✅ LangChain loaded {len(documents)} articles")
        
        # Process documents into our database format
        articles_to_insert = []
        
        for doc in documents:
            # Find which feed this came from
            source_url = doc.metadata.get('source', '')
            feed_url = None
            
            # Try to match source to our feeds
            for url in all_urls:
                if url in source_url or source_url in url:
                    feed_url = url
                    break
            
            if not feed_url:
                # Fallback: try to guess from domain
                import re
                domain_match = re.search(r'https?://([^/]+)', source_url)
                if domain_match:
                    domain = domain_match.group(1)
                    for url in all_urls:
                        if domain in url:
                            feed_url = url
                            break
            
            if not feed_url:
                # If still can't match, use first feed with matching name in metadata
                source_name = doc.metadata.get('source', '').lower()
                for perspective, feeds in RSS_FEEDS.items():
                    for feed in feeds:
                        if feed['name'].lower() in source_name:
                            feed_url = feed['feed_url']
                            break
            
            source_info = source_map.get(feed_url, {
                'name': doc.metadata.get('source', 'Unknown'),
                'website': doc.metadata.get('link', '').split('/')[2] if doc.metadata.get('link') else '',
                'perspective': 'centrist',  # Default
                'category': 'general'
            })
            
            # Generate unique GUID
            guid = doc.metadata.get('id', doc.metadata.get('link', str(hash(doc.page_content[:100]))))
            
            # Extract image from metadata or content
            image_url = None
            if 'image' in doc.metadata:
                image_url = doc.metadata['image']
            elif 'media' in doc.metadata:
                image_url = doc.metadata['media']
            
            # Fallback to source logo
            if not image_url and source_info['website']:
                image_url = f"https://logo.clearbit.com/{source_info['website'].replace('https://', '').replace('http://', '').split('/')[0]}"
            
            # Get summary (either from metadata or create from content)
            summary = doc.metadata.get('summary', '')
            if not summary and doc.page_content:
                summary = doc.page_content[:300] + '...'
            
            # Get keywords as JSON
            keywords = json.dumps(doc.metadata.get('keywords', []))
            
            # Parse publish date
            published = None
            if 'publish_date' in doc.metadata:
                published = doc.metadata['publish_date']
            elif 'published' in doc.metadata:
                published = doc.metadata['published']
            
            articles_to_insert.append((
                guid,
                doc.metadata.get('title', 'Untitled'),
                summary,
                doc.page_content,
                doc.metadata.get('link', '#'),
                image_url,
                source_info['name'],
                source_info['website'],
                source_info['perspective'],
                keywords,
                published
            ))
        
        return articles_to_insert
        
    except Exception as e:
        print(f"❌ LangChain RSS loading error: {e}")
        return []

def store_articles(articles):
    """Store fetched articles in database"""
    if not articles:
        return 0
    
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    
    inserted = 0
    for article in articles:
        try:
            c.execute('''INSERT OR IGNORE INTO articles 
                       (guid, title, summary, content, link, image_url,
                        source_name, source_url, perspective, keywords, published)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', article)
            if c.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"Error inserting article: {e}")
    
    conn.commit()
    conn.close()
    return inserted

def refresh_article_database():
    """Main function to refresh articles from RSS feeds"""
    print("🔄 Starting RSS feed refresh...")
    articles = fetch_with_langchain()
    if articles:
        count = store_articles(articles)
        print(f"✅ Stored {count} new articles")
        return count
    return 0

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

def get_user_preferences(user_id):
    """Get user's preferred perspective based on interactions"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''SELECT a.perspective, COUNT(*) as cnt 
                 FROM interactions i
                 JOIN articles a ON i.article_id = a.id
                 WHERE i.user_id = ? AND i.action IN ('view', 'interested', 'rate_informative')
                 GROUP BY a.perspective''', (user_id,))
    
    prefs = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    
    return prefs

def generate_content_batch(condition, user_id, limit=5, seen_ids=None):
    """Generate batch of articles based on condition"""
    if seen_ids is None:
        seen_ids = []
    
    conn = get_db()
    c = conn.cursor()
    
    # Check if we need to refresh feeds
    c.execute('SELECT COUNT(*) FROM articles')
    total_articles = c.fetchone()[0]
    
    if total_articles < 50:
        # Low on articles, trigger refresh in background
        # In production, you'd use a background task
        refresh_article_database()
    
    if condition == 'normal':
        # FILTER BUBBLE: Weight toward preferred perspective
        prefs = get_user_preferences(user_id)
        
        if not prefs:
            # First time user - start balanced
            perspectives = ['progressive', 'centrist', 'conservative']
            weights = [1, 1, 1]
        else:
            total = sum(prefs.values())
            # Convert counts to weights with slight randomization
            weights = [
                prefs.get('progressive', 0) / total + random.uniform(-0.1, 0.1),
                prefs.get('centrist', 0) / total + random.uniform(-0.1, 0.1),
                prefs.get('conservative', 0) / total + random.uniform(-0.1, 0.1)
            ]
            # Normalize
            total_weight = sum(weights)
            weights = [w/total_weight for w in weights]
        
        # Select articles with perspective weighting
        articles = []
        for _ in range(limit):
            perspective = random.choices(
                ['progressive', 'centrist', 'conservative'],
                weights=weights
            )[0]
            
            placeholders = ','.join(['?'] * len(seen_ids)) if seen_ids else '0'
            c.execute(f'''SELECT * FROM articles 
                         WHERE perspective = ? AND id NOT IN ({placeholders})
                         ORDER BY RANDOM() LIMIT 1''',
                      [perspective] + (seen_ids if seen_ids else []))
            article = c.fetchone()
            
            if article:
                articles.append(dict(article))
                seen_ids.append(article['id'])
    
    else:
        # DIVERSE: Equal representation
        perspectives = ['progressive', 'centrist', 'conservative']
        per_perspective = limit // 3 + 1
        
        for perspective in perspectives:
            placeholders = ','.join(['?'] * len(seen_ids)) if seen_ids else '0'
            c.execute(f'''SELECT * FROM articles 
                         WHERE perspective = ? AND id NOT IN ({placeholders})
                         ORDER BY RANDOM() LIMIT ?''',
                      [perspective] + (seen_ids if seen_ids else []) + [per_perspective])
            batch = [dict(row) for row in c.fetchall()]
            articles.extend(batch)
            seen_ids.extend([a['id'] for a in batch])
        
        articles = articles[:limit]
    
    random.shuffle(articles)
    conn.close()
    
    return articles

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

@app.route('/feed')
@login_required
def feed():
    user_id = session['user_id']
    condition = session['condition']
    
    # Get initial batch
    initial_batch = generate_content_batch(condition, user_id)
    
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
                                 initial_batch=json.dumps(initial_batch, default=str))

@app.route('/api/load_more', methods=['POST'])
@login_required
def load_more():
    data = request.json
    user_id = session['user_id']
    condition = session['condition']
    seen_ids = data.get('seen_ids', [])
    
    new_batch = generate_content_batch(condition, user_id, limit=3, seen_ids=seen_ids)
    
    return jsonify({
        'items': new_batch,
        'has_more': len(new_batch) > 0
    })

@app.route('/api/log_interaction', methods=['POST'])
@login_required
def log_interaction():
    data = request.json
    user_id = session['user_id']
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO interactions 
                 (user_id, article_id, timestamp, action, time_spent, expand_duration, rating)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, data.get('article_id'), datetime.now(), 
               data.get('action'), data.get('time_spent', 0),
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

@app.route('/admin')
def admin():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT condition, COUNT(*) FROM users GROUP BY condition")
    condition_counts = dict(c.fetchall())
    
    c.execute("SELECT COUNT(*) FROM articles")
    total_articles = c.fetchone()[0]
    
    c.execute("SELECT perspective, COUNT(*) FROM articles GROUP BY perspective")
    article_perspectives = dict(c.fetchall())
    
    c.execute("SELECT COUNT(*) FROM interactions")
    total_interactions = c.fetchone()[0]
    
    c.execute('''SELECT u.id, i.timestamp, a.perspective, a.source_name, i.action 
                 FROM interactions i
                 JOIN users u ON i.user_id = u.id
                 JOIN articles a ON i.article_id = a.id
                 ORDER BY i.timestamp DESC LIMIT 20''')
    recent = c.fetchall()
    
    c.execute('SELECT COUNT(*) as cnt, perspective FROM articles GROUP BY perspective')
    perspective_counts = c.fetchall()
    
    conn.close()
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PolitiScope Admin</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .stat-card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #333; }}
            table {{ width: 100%; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); border-collapse: collapse; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
            .badge {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }}
            .badge-progressive {{ background: #ff6b6b20; color: #ff6b6b; }}
            .badge-centrist {{ background: #4ecdc420; color: #4ecdc4; }}
            .badge-conservative {{ background: #45b7d120; color: #45b7d1; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔬 PolitiScope Admin Dashboard</h1>
                <p>LangChain-Powered RSS News Aggregator</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total Users</h3>
                    <div class="stat-number">{total_users}</div>
                </div>
                <div class="stat-card">
                    <h3>Normal (Filter Bubble)</h3>
                    <div class="stat-number">{condition_counts.get('normal', 0)}</div>
                </div>
                <div class="stat-card">
                    <h3>Diverse (Balanced)</h3>
                    <div class="stat-number">{condition_counts.get('diverse', 0)}</div>
                </div>
                <div class="stat-card">
                    <h3>Articles in DB</h3>
                    <div class="stat-number">{total_articles}</div>
                </div>
                <div class="stat-card">
                    <h3>Total Interactions</h3>
                    <div class="stat-number">{total_interactions}</div>
                </div>
            </div>
            
            <h2>Article Perspectives</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Progressive</h3>
                    <div class="stat-number">{article_perspectives.get('progressive', 0)}</div>
                </div>
                <div class="stat-card">
                    <h3>Centrist</h3>
                    <div class="stat-number">{article_perspectives.get('centrist', 0)}</div>
                </div>
                <div class="stat-card">
                    <h3>Conservative</h3>
                    <div class="stat-number">{article_perspectives.get('conservative', 0)}</div>
                </div>
            </div>
            
            <h2>Recent Activity</h2>
            <table>
                <tr>
                    <th>User ID</th>
                    <th>Time</th>
                    <th>Source</th>
                    <th>Perspective</th>
                    <th>Action</th>
                </tr>
                {"".join(f"<tr><td>{r[0]}</td><td>{r[1][:19]}</td><td>{r[3]}</td><td><span class='badge badge-{r[2]}'>{r[2]}</span></td><td>{r[4]}</td></tr>" for r in recent)}
            </table>
            
            <div style="margin-top: 30px; text-align: center;">
                <a href="/api/refresh_now" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 8px;">🔄 Refresh Feeds Now</a>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return html

@app.route('/api/refresh_now')
def refresh_now():
    """Manual trigger for feed refresh"""
    count = refresh_article_database()
    return f"✅ Refreshed! Added {count} new articles. <a href='/admin'>Back to Admin</a>"

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
        .footer { margin-top: 30px; font-size: 0.8em; color: #999; }
        .footer a { color: #667eea; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 PolitiScope</h1>
        <p class="subtitle">Real News from Trusted Sources • Research Study</p>
        
        <div class="btn-container">
            <button class="btn" onclick="register()">🆕 New Participant</button>
            <button class="btn btn-secondary" onclick="login()">🔑 Returning</button>
        </div>
        <div class="footer">
            <p>Pulling from 20+ news sources • Updated hourly</p>
            <p><a href="/admin">Admin Dashboard</a></p>
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
            max-width: 800px;
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
            max-width: 800px;
            margin-left: auto;
            margin-right: auto;
        }
        .timer-display {
            font-size: 3em;
            font-family: monospace;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
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
            max-width: 800px;
            margin: 0 auto;
        }
        .content-card {
            background: {{ '#1a1a1a' if theme == 'dark' else 'white' }};
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 4px 12px {{ 'rgba(0,0,0,0.3)' if theme == 'dark' else 'rgba(0,0,0,0.1)' }};
            border-left: 6px solid;
        }
        .progressive { border-left-color: #ff6b6b; }
        .centrist { border-left-color: #4ecdc4; }
        .conservative { border-left-color: #45b7d1; }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        .badge-progressive { background: #ff6b6b20; color: #ff6b6b; }
        .badge-centrist { background: #4ecdc420; color: #4ecdc4; }
        .badge-conservative { background: #45b7d120; color: #45b7d1; }
        .source-name {
            font-size: 14px;
            color: #888;
        }
        h2 { font-size: 1.5em; margin-bottom: 10px; line-height: 1.3; }
        .summary {
            font-size: 1.1em;
            color: {{ '#ccc' if theme == 'dark' else '#555' }};
            margin-bottom: 15px;
            line-height: 1.6;
        }
        .article-image {
            width: 100%;
            max-height: 300px;
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
        .full-article {
            line-height: 1.8;
            margin-bottom: 20px;
        }
        .source-link {
            display: inline-block;
            margin: 10px 0;
            padding: 8px 16px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 20px;
            font-size: 14px;
        }
        .source-link:hover {
            background: #5a6fd8;
        }
        .keywords {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 15px 0;
        }
        .keyword {
            background: {{ '#333' if theme == 'dark' else '#f0f0f0' }};
            color: {{ '#fff' if theme == 'dark' else '#333' }};
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 12px;
        }
        .buttons {
            display: flex;
            gap: 10px;
            margin: 20px 0 10px;
            flex-wrap: wrap;
        }
        .btn {
            flex: 1;
            min-width: 100px;
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
        .loading {
            text-align: center;
            padding: 30px;
            color: #888;
        }
        .infinite-scroll-trigger {
            height: 20px;
            margin: 30px 0;
            text-align: center;
        }
        .published-date {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
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
        <div class="target-time">Target: 20 minutes • Endless news from trusted sources</div>
    </div>
    
    <div class="feed-container" id="feed"></div>
    <div class="infinite-scroll-trigger" id="scrollTrigger"></div>
    <div class="loading" id="loading" style="display: none;">📰 Loading more news...</div>
    
    <button class="theme-toggle" onclick="toggleTheme()">
        {{ '☀️ Light' if theme == 'dark' else '🌙 Dark' }}
    </button>
    
    <button class="exit-btn" onclick="exitSession()">✕ Exit</button>
    
    <script>
        const userId = '{{ user_id }}';
        const condition = '{{ condition }}';
        const initialBatch = {{ initial_batch | safe }};
        
        let allItems = [...initialBatch];
        let seenIds = new Set(initialBatch.map(item => item.id));
        let startTime = Date.now();
        let expandTimes = {};
        let cardStartTimes = {};
        let isLoading = false;
        let currentPage = 1;
        
        console.log('🔬 Research condition for user', userId + ':', condition);
        console.log('Initial feed loaded with', allItems.length, 'articles');
        
        // Render feed
        function renderFeed() {
            const feed = document.getElementById('feed');
            if (!feed) return;
            
            feed.innerHTML = '';
            allItems.forEach((item, index) => {
                const card = createCard(item, index);
                feed.appendChild(card);
            });
            
            setupInfiniteScroll();
        }
        
        function createCard(item, index) {
            const card = document.createElement('div');
            card.className = `content-card ${item.perspective}`;
            card.dataset.articleId = item.id;
            card.dataset.index = index;
            
            const perspectiveEmoji = item.perspective === 'progressive' ? '🔴' : 
                                    item.perspective === 'centrist' ? '⚪' : '🔵';
            
            // Parse keywords if present
            let keywords = [];
            try {
                if (item.keywords) {
                    keywords = JSON.parse(item.keywords);
                }
            } catch (e) {
                // Not JSON, ignore
            }
            
            // Format date
            let publishedDate = '';
            if (item.published) {
                const date = new Date(item.published);
                publishedDate = date.toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric',
                    year: 'numeric'
                });
            }
            
            card.innerHTML = `
                <div>
                    <div class="card-header">
                        <span class="badge badge-${item.perspective}">
                            ${perspectiveEmoji} ${item.perspective.toUpperCase()}
                        </span>
                        <span class="source-name">📰 ${item.source_name || 'Unknown Source'}</span>
                    </div>
                    
                    <h2>${item.title || 'Untitled'}</h2>
                    <div class="summary">${item.summary || ''}</div>
                    
                    ${item.image_url ? `<img class="article-image" src="${item.image_url}" alt="Article image" onerror="this.style.display='none'">` : ''}
                    
                    <button class="expand-btn" onclick="toggleExpand(this, ${item.id})">
                        ▼ Read Full Analysis
                    </button>
                    
                    <div class="expanded-content" id="expand-${item.id}">
                        <div class="full-article">${item.content || 'Full content available at source.'}</div>
                        
                        ${keywords.length > 0 ? `
                            <div class="keywords">
                                ${keywords.slice(0, 5).map(k => `<span class="keyword">#${k}</span>`).join('')}
                            </div>
                        ` : ''}
                        
                        <a href="${item.link}" target="_blank" class="source-link">📖 Read at ${item.source_name || 'Source'}</a>
                        
                        ${publishedDate ? `<div class="published-date">Published: ${publishedDate}</div>` : ''}
                    </div>
                </div>
                
                <div>
                    <div class="buttons">
                        <button class="btn btn-interested" onclick="markInterested(${item.id}, this)">
                            🔖 Interested
                        </button>
                        <button class="btn btn-informative" onclick="rateContent(${item.id}, 'informative')">
                            ✅ Informative
                        </button>
                        <button class="btn btn-not-useful" onclick="rateContent(${item.id}, 'not_useful')">
                            ❌ Not Useful
                        </button>
                    </div>
                </div>
            `;
            
            return card;
        }
        
        // Infinite scroll setup
        function setupInfiniteScroll() {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting && !isLoading) {
                        loadMoreContent();
                    }
                });
            });
            
            const trigger = document.getElementById('scrollTrigger');
            if (trigger) {
                observer.observe(trigger);
            }
        }
        
        // Load more content from server
        async function loadMoreContent() {
            if (isLoading) return;
            
            isLoading = true;
            document.getElementById('loading').style.display = 'block';
            
            try {
                const res = await fetch('/api/load_more', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        seen_ids: Array.from(seenIds)
                    })
                });
                
                const data = await res.json();
                
                if (data.items && data.items.length > 0) {
                    data.items.forEach(item => {
                        if (!seenIds.has(item.id)) {
                            allItems.push(item);
                            seenIds.add(item.id);
                        }
                    });
                    
                    renderFeed();
                }
                
            } catch (error) {
                console.error('Error loading more content:', error);
            } finally {
                isLoading = false;
                document.getElementById('loading').style.display = 'none';
            }
        }
        
        // Expand/collapse tracking
        function toggleExpand(btn, articleId) {
            const expanded = document.getElementById(`expand-${articleId}`);
            const isExpanding = expanded.style.display === 'none';
            
            if (isExpanding) {
                expanded.style.display = 'block';
                btn.innerHTML = '▲ Collapse Analysis';
                expandTimes[articleId] = Date.now();
                
                fetch('/api/log_interaction', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        article_id: articleId,
                        action: 'expand_start'
                    })
                });
            } else {
                expanded.style.display = 'none';
                btn.innerHTML = '▼ Read Full Analysis';
                
                if (expandTimes[articleId]) {
                    const duration = Math.floor((Date.now() - expandTimes[articleId]) / 1000);
                    
                    fetch('/api/log_interaction', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            article_id: articleId,
                            action: 'expand_end',
                            expand_duration: duration
                        })
                    });
                    
                    delete expandTimes[articleId];
                }
            }
        }
        
        // Interested button
        function markInterested(articleId, btn) {
            btn.classList.add('active');
            btn.textContent = '✓ Interested';
            
            fetch('/api/log_interaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    article_id: articleId,
                    action: 'interested'
                })
            });
            
            alert('✅ Thanks! Your interest has been recorded.');
        }
        
        // Rate content
        function rateContent(articleId, rating) {
            fetch('/api/log_interaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    article_id: articleId,
                    action: 'rate',
                    rating: rating
                })
            });
            
            alert(rating === 'informative' ? '✅ Rated as informative' : '❌ Rated as not useful');
        }
        
        // Timer and progress
        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            const timeString = `${mins.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}`;
            
            document.getElementById('timer').textContent = timeString;
            document.getElementById('bigTimer').textContent = timeString;
            
            const progress = Math.min((elapsed / 1200) * 100, 100);
            document.getElementById('progressFill').style.width = progress + '%';
        }
        
        // Exit session
        function exitSession() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            
            if (confirm(`⏱️ You spent ${mins}:${secs.toString().padStart(2,'0')} minutes today.\\n\\nExit to homepage?`)) {
                window.location.href = '/';
            }
        }
        
        // Toggle theme
        async function toggleTheme() {
            const isDark = document.body.classList.contains('dark');
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
            
            // Log view for first card when user scrolls to it
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const card = entry.target;
                        const articleId = card.dataset.articleId;
                        const index = parseInt(card.dataset.index);
                        
                        if (!cardStartTimes[index]) {
                            cardStartTimes[index] = Date.now();
                        }
                    }
                });
            }, { threshold: 0.5 });
            
            // Observe all cards
            setTimeout(() => {
                document.querySelectorAll('.content-card').forEach(card => {
                    observer.observe(card);
                });
            }, 500);
        });
        
        // Log view time when leaving page
        window.addEventListener('beforeunload', function() {
            Object.keys(cardStartTimes).forEach(index => {
                const timeSpent = Math.floor((Date.now() - cardStartTimes[index]) / 1000);
                if (timeSpent > 2) {  // Only log if spent more than 2 seconds
                    const card = document.querySelector(`[data-index="${index}"]`);
                    if (card) {
                        const articleId = card.dataset.articleId;
                        navigator.sendBeacon('/api/log_interaction', JSON.stringify({
                            article_id: parseInt(articleId),
                            action: 'view',
                            time_spent: timeSpent
                        }));
                    }
                }
            });
        });
    </script>
</body>
</html>
'''

# ==================== INITIAL DATA LOAD ====================
# Run once at startup to populate database
with app.app_context():
    refresh_article_database()

# ==================== RUN APPLICATION ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
