import os
import random
import sqlite3
import json
import requests
import feedparser
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from functools import wraps
import time
from googleapiclient.discovery import build
from newspaper import Article
import re

app = Flask(__name__)
app.secret_key = 'politiscope-secret-key-change-this'
application = app

# ==================== API KEYS ====================
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')  # Get from Google Cloud Console
if not YOUTUBE_API_KEY:
    print("⚠️  WARNING: Set YOUTUBE_API_KEY in environment variables")

# ==================== CONTENT SOURCES ====================
# Real video sources (YouTube channels)
VIDEO_SOURCES = {
    'progressive': [
        {
            'name': 'Vox',
            'channel_id': 'UCLXo7UDZvByw2ixzpQCufnA',
            'type': 'youtube'
        },
        {
            'name': 'The Young Turks',
            'channel_id': 'UC1yBKRuGpC1tSM73A0ZjYjQ',
            'type': 'youtube'
        },
        {
            'name': 'NowThis News',
            'channel_id': 'UCjZ7Y42HUTNfQP7tA-n42Kw',
            'type': 'youtube'
        }
    ],
    'conservative': [
        {
            'name': 'Fox News',
            'channel_id': 'UCXIJgqnII2ZOINSWNOGFThA',
            'type': 'youtube'
        },
        {
            'name': 'Ben Shapiro',
            'channel_id': 'UCnQC_G5Xsjhp9fEJKuIcrSw',
            'type': 'youtube'
        },
        {
            'name': 'PragerU',
            'channel_id': 'UCZW5lIUz93q_aZIkJPAC0IQ',
            'type': 'youtube'
        }
    ],
    'centrist': [
        {
            'name': 'Associated Press',
            'channel_id': 'UC52X5wxOL_s5yw0dQk7NtgA',
            'type': 'youtube'
        },
        {
            'name': 'Reuters',
            'channel_id': 'UCqj8mrCv4oASRlU-o_bDkKA',
            'type': 'youtube'
        },
        {
            'name': 'BBC News',
            'channel_id': 'UC16niRr50-MSBwiO3YDb3RA',
            'type': 'youtube'
        }
    ]
}

# Long-form article sources (WordPress/Medium feeds)
ARTICLE_SOURCES = {
    'progressive': [
        {
            'name': 'The Atlantic',
            'feed_url': 'https://www.theatlantic.com/feed/all/',
            'type': 'wordpress'
        },
        {
            'name': 'The New Yorker',
            'feed_url': 'https://www.newyorker.com/feed/news',
            'type': 'wordpress'
        },
        {
            'name': 'Mother Jones',
            'feed_url': 'https://www.motherjones.com/feed/',
            'type': 'wordpress'
        }
    ],
    'conservative': [
        {
            'name': 'National Review',
            'feed_url': 'https://www.nationalreview.com/feed/',
            'type': 'wordpress'
        },
        {
            'name': 'The Federalist',
            'feed_url': 'https://thefederalist.com/feed/',
            'type': 'wordpress'
        },
        {
            'name': 'Washington Examiner',
            'feed_url': 'https://www.washingtonexaminer.com/feed',
            'type': 'wordpress'
        }
    ],
    'centrist': [
        {
            'name': 'Reuters',
            'feed_url': 'https://feeds.reuters.com/news/politics',
            'type': 'wordpress'
        },
        {
            'name': 'AP News',
            'feed_url': 'https://feeds.ap.org/feeds/feed/APTopNews',
            'type': 'wordpress'
        },
        {
            'name': 'The Hill',
            'feed_url': 'https://thehill.com/feed/',
            'type': 'wordpress'
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
    
    # Videos table (real videos)
    c.execute('''CREATE TABLE IF NOT EXISTS videos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  video_id TEXT UNIQUE,
                  title TEXT,
                  description TEXT,
                  channel_name TEXT,
                  channel_id TEXT,
                  perspective TEXT,
                  duration TEXT,
                  view_count INTEGER,
                  like_count INTEGER,
                  comment_count INTEGER,
                  published_at TIMESTAMP,
                  thumbnail_url TEXT,
                  embed_url TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Articles table (long-form articles)
    c.execute('''CREATE TABLE IF NOT EXISTS articles
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guid TEXT UNIQUE,
                  title TEXT,
                  content TEXT,  # Full article content
                  summary TEXT,
                  source_name TEXT,
                  source_url TEXT,
                  perspective TEXT,
                  author TEXT,
                  published TIMESTAMP,
                  image_url TEXT,
                  word_count INTEGER,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Interactions table
    c.execute('''CREATE TABLE IF NOT EXISTS interactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  content_id INTEGER,
                  content_type TEXT,  # 'video' or 'article'
                  timestamp TIMESTAMP,
                  action TEXT,
                  time_spent INTEGER,
                  expand_duration INTEGER,
                  rating TEXT)''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

init_database()

# ==================== YOUTUBE FETCHER ====================
def fetch_youtube_videos(channel_id, max_results=10):
    """Fetch real videos from YouTube channel"""
    if not YOUTUBE_API_KEY:
        return []
    
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # Get channel's uploads playlist
        channels_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()
        
        if not channels_response['items']:
            return []
        
        uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Get videos from playlist
        videos = []
        next_page_token = None
        
        while len(videos) < max_results:
            playlist_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=min(50, max_results - len(videos)),
                pageToken=next_page_token
            ).execute()
            
            video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response['items']]
            
            # Get video details (duration, stats)
            if video_ids:
                videos_response = youtube.videos().list(
                    part='contentDetails,statistics,snippet',
                    id=','.join(video_ids)
                ).execute()
                
                for video in videos_response['items']:
                    videos.append({
                        'video_id': video['id'],
                        'title': video['snippet']['title'],
                        'description': video['snippet']['description'],
                        'published_at': video['snippet']['publishedAt'],
                        'thumbnail_url': video['snippet']['thumbnails']['high']['url'],
                        'duration': video['contentDetails']['duration'],
                        'view_count': int(video['statistics'].get('viewCount', 0)),
                        'like_count': int(video['statistics'].get('likeCount', 0)),
                        'comment_count': int(video['statistics'].get('commentCount', 0)),
                        'embed_url': f"https://www.youtube.com/embed/{video['id']}"
                    })
            
            next_page_token = playlist_response.get('nextPageToken')
            if not next_page_token:
                break
        
        return videos[:max_results]
        
    except Exception as e:
        print(f"❌ YouTube API error: {e}")
        return []

# ==================== ARTICLE FETCHER (with full content) ====================
def fetch_full_article(url):
    """Use newspaper3k to get full article content"""
    try:
        article = Article(url)
        article.download()
        article.parse()
        article.nlp()
        
        return {
            'title': article.title,
            'content': article.text,
            'summary': article.summary,
            'keywords': article.keywords,
            'authors': article.authors,
            'publish_date': article.publish_date,
            'top_image': article.top_image,
            'videos': article.movies,  # Actual videos in the article
            'word_count': len(article.text.split())
        }
    except Exception as e:
        print(f"❌ Error fetching article {url}: {e}")
        return None

def fetch_articles_from_feed(feed_url, perspective, max_articles=5):
    """Fetch articles from RSS feed and get full content"""
    articles = []
    
    try:
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:max_articles]:
            # Get full article content
            full_article = fetch_full_article(entry.link)
            
            if full_article:
                articles.append({
                    'guid': entry.get('id', entry.link),
                    'title': full_article['title'],
                    'content': full_article['content'],
                    'summary': full_article['summary'],
                    'source_name': feed.feed.get('title', 'Unknown'),
                    'source_url': entry.link,
                    'perspective': perspective,
                    'author': ', '.join(full_article['authors']),
                    'published': full_article['publish_date'],
                    'image_url': full_article['top_image'],
                    'word_count': full_article['word_count'],
                    'keywords': json.dumps(full_article['keywords'])
                })
            
            time.sleep(1)  # Be nice to servers
        
        return articles
        
    except Exception as e:
        print(f"❌ Error fetching feed {feed_url}: {e}")
        return []

# ==================== CONTENT REFRESH FUNCTIONS ====================
def refresh_video_database():
    """Fetch latest videos from all YouTube channels"""
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    
    total_added = 0
    
    for perspective, channels in VIDEO_SOURCES.items():
        for channel in channels:
            print(f"📹 Fetching videos from {channel['name']}...")
            videos = fetch_youtube_videos(channel['channel_id'], max_results=10)
            
            for video in videos:
                try:
                    c.execute('''INSERT OR IGNORE INTO videos 
                               (video_id, title, description, channel_name, channel_id,
                                perspective, duration, view_count, like_count,
                                comment_count, published_at, thumbnail_url, embed_url)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (video['video_id'], video['title'], video['description'],
                             channel['name'], channel['channel_id'], perspective,
                             video['duration'], video['view_count'], video['like_count'],
                             video['comment_count'], video['published_at'],
                             video['thumbnail_url'], video['embed_url']))
                    
                    if c.rowcount > 0:
                        total_added += 1
                        
                except Exception as e:
                    print(f"Error storing video {video['video_id']}: {e}")
            
            time.sleep(1)  # YouTube API rate limits
    
    conn.commit()
    conn.close()
    print(f"✅ Added {total_added} new videos")
    return total_added

def refresh_article_database():
    """Fetch latest articles from all sources with full content"""
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    
    total_added = 0
    
    for perspective, sources in ARTICLE_SOURCES.items():
        for source in sources:
            print(f"📰 Fetching articles from {source['name']}...")
            articles = fetch_articles_from_feed(source['feed_url'], perspective)
            
            for article in articles:
                try:
                    c.execute('''INSERT OR IGNORE INTO articles 
                               (guid, title, content, summary, source_name,
                                source_url, perspective, author, published,
                                image_url, word_count, keywords)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (article['guid'], article['title'], article['content'],
                             article['summary'], article['source_name'],
                             article['source_url'], article['perspective'],
                             article['author'], article['published'],
                             article['image_url'], article['word_count'],
                             article['keywords']))
                    
                    if c.rowcount > 0:
                        total_added += 1
                        
                except Exception as e:
                    print(f"Error storing article {article['guid']}: {e}")
            
            time.sleep(2)  # Be nice to servers
    
    conn.commit()
    conn.close()
    print(f"✅ Added {total_added} new articles")
    return total_added

# ==================== CONTENT GENERATION ====================
def get_user_preferences(user_id):
    """Get user's preferred perspective based on interactions"""
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    
    c.execute('''SELECT a.perspective, COUNT(*) as cnt 
                 FROM interactions i
                 JOIN articles a ON i.content_id = a.id
                 WHERE i.user_id = ? AND i.action IN ('view', 'interested', 'rate_informative')
                 AND i.content_type = 'article'
                 GROUP BY a.perspective''', (user_id,))
    
    article_prefs = {row[0]: row[1] for row in c.fetchall()}
    
    c.execute('''SELECT v.perspective, COUNT(*) as cnt 
                 FROM interactions i
                 JOIN videos v ON i.content_id = v.id
                 WHERE i.user_id = ? AND i.action IN ('view', 'interested', 'rate_informative')
                 AND i.content_type = 'video'
                 GROUP BY v.perspective''', (user_id,))
    
    video_prefs = {row[0]: row[1] for row in c.fetchall()}
    
    conn.close()
    
    # Combine preferences
    combined = {}
    for p in ['progressive', 'centrist', 'conservative']:
        combined[p] = article_prefs.get(p, 0) + video_prefs.get(p, 0)
    
    return combined

def generate_content_batch(condition, user_id, limit=5, seen_ids=None):
    """Generate mixed batch of videos and articles"""
    if seen_ids is None:
        seen_ids = {'videos': [], 'articles': []}
    
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    
    # Mix videos and articles (60% articles, 40% videos)
    article_count = int(limit * 0.6)
    video_count = limit - article_count
    
    articles = []
    videos = []
    
    if condition == 'normal':
        # Filter bubble based on preferences
        prefs = get_user_preferences(user_id)
        
        if not prefs or sum(prefs.values()) == 0:
            weights = [1, 1, 1]
        else:
            total = sum(prefs.values())
            weights = [
                prefs.get('progressive', 0) / total,
                prefs.get('centrist', 0) / total,
                prefs.get('conservative', 0) / total
            ]
        
        # Get articles with weighting
        perspectives = ['progressive', 'centrist', 'conservative']
        for _ in range(article_count):
            perspective = random.choices(perspectives, weights=weights)[0]
            
            placeholders = ','.join(['?'] * len(seen_ids['articles'])) if seen_ids['articles'] else '0'
            c.execute(f'''SELECT * FROM articles 
                         WHERE perspective = ? AND id NOT IN ({placeholders})
                         ORDER BY RANDOM() LIMIT 1''',
                      [perspective] + (seen_ids['articles'] if seen_ids['articles'] else []))
            article = c.fetchone()
            
            if article:
                articles.append(dict(article))
                seen_ids['articles'].append(article['id'])
        
        # Get videos with same weighting
        for _ in range(video_count):
            perspective = random.choices(perspectives, weights=weights)[0]
            
            placeholders = ','.join(['?'] * len(seen_ids['videos'])) if seen_ids['videos'] else '0'
            c.execute(f'''SELECT * FROM videos 
                         WHERE perspective = ? AND id NOT IN ({placeholders})
                         ORDER BY RANDOM() LIMIT 1''',
                      [perspective] + (seen_ids['videos'] if seen_ids['videos'] else []))
            video = c.fetchone()
            
            if video:
                videos.append(dict(video))
                seen_ids['videos'].append(video['id'])
    
    else:
        # Diverse - balanced across perspectives
        perspectives = ['progressive', 'centrist', 'conservative']
        
        # Get articles evenly
        per_perspective = article_count // 3 + 1
        for perspective in perspectives:
            placeholders = ','.join(['?'] * len(seen_ids['articles'])) if seen_ids['articles'] else '0'
            c.execute(f'''SELECT * FROM articles 
                         WHERE perspective = ? AND id NOT IN ({placeholders})
                         ORDER BY RANDOM() LIMIT ?''',
                      [perspective] + (seen_ids['articles'] if seen_ids['articles'] else []) + [per_perspective])
            batch = [dict(row) for row in c.fetchall()]
            articles.extend(batch)
            seen_ids['articles'].extend([a['id'] for a in batch])
        
        # Get videos evenly
        per_perspective = video_count // 3 + 1
        for perspective in perspectives:
            placeholders = ','.join(['?'] * len(seen_ids['videos'])) if seen_ids['videos'] else '0'
            c.execute(f'''SELECT * FROM videos 
                         WHERE perspective = ? AND id NOT IN ({placeholders})
                         ORDER BY RANDOM() LIMIT ?''',
                      [perspective] + (seen_ids['videos'] if seen_ids['videos'] else []) + [per_perspective])
            batch = [dict(row) for row in c.fetchall()]
            videos.extend(batch)
            seen_ids['videos'].extend([v['id'] for v in batch])
    
    # Mix and shuffle
    combined = []
    for article in articles[:article_count]:
        combined.append({
            'type': 'article',
            'data': article
        })
    
    for video in videos[:video_count]:
        combined.append({
            'type': 'video',
            'data': video
        })
    
    random.shuffle(combined)
    conn.close()
    
    return combined

# ==================== ROUTES ====================
@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/register', methods=['POST'])
def register():
    conn = sqlite3.connect('politiscope.db')
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
    
    conn = sqlite3.connect('politiscope.db')
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
def feed():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    user_id = session['user_id']
    condition = session['condition']
    
    # Check if we need initial data
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM articles')
    article_count = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM videos')
    video_count = c.fetchone()[0]
    conn.close()
    
    if article_count < 10 or video_count < 5:
        # First run - populate database
        refresh_article_database()
        refresh_video_database()
    
    # Get initial batch
    initial_batch = generate_content_batch(condition, user_id, limit=8)
    
    # Get user theme
    conn = sqlite3.connect('politiscope.db')
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
def load_more():
    if 'user_id' not in session:
        return jsonify({'items': []})
    
    data = request.json
    user_id = session['user_id']
    condition = session['condition']
    seen_ids = data.get('seen_ids', {'videos': [], 'articles': []})
    
    new_batch = generate_content_batch(condition, user_id, limit=4, seen_ids=seen_ids)
    
    return jsonify({
        'items': new_batch,
        'seen_ids': seen_ids
    })

@app.route('/api/log_interaction', methods=['POST'])
def log_interaction():
    if 'user_id' not in session:
        return jsonify({"status": "error"})
    
    data = request.json
    user_id = session['user_id']
    
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    c.execute('''INSERT INTO interactions 
                 (user_id, content_id, content_type, timestamp, action, time_spent, expand_duration, rating)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, data.get('content_id'), data.get('content_type'),
               datetime.now(), data.get('action'), 
               data.get('time_spent', 0), data.get('expand_duration'), 
               data.get('rating')))
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

@app.route('/admin')
def admin():
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM videos")
    total_videos = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM articles")
    total_articles = c.fetchone()[0]
    
    c.execute("SELECT perspective, COUNT(*) FROM videos GROUP BY perspective")
    video_perspectives = dict(c.fetchall())
    
    c.execute("SELECT perspective, COUNT(*) FROM articles GROUP BY perspective")
    article_perspectives = dict(c.fetchall())
    
    c.execute("SELECT COUNT(*) FROM interactions")
    total_interactions = c.fetchone()[0]
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PolitiScope Admin</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }}
            .stat-card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #333; }}
            .button {{ background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 8px; display: inline-block; margin: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔬 PolitiScope Admin Dashboard</h1>
                <p>Real Videos & Long-Form Articles</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total Users</h3>
                    <div class="stat-number">{total_users}</div>
                </div>
                <div class="stat-card">
                    <h3>Videos</h3>
                    <div class="stat-number">{total_videos}</div>
                </div>
                <div class="stat-card">
                    <h3>Articles</h3>
                    <div class="stat-number">{total_articles}</div>
                </div>
                <div class="stat-card">
                    <h3>Interactions</h3>
                    <div class="stat-number">{total_interactions}</div>
                </div>
            </div>
            
            <h2>Actions</h2>
            <a href="/api/refresh_videos" class="button">🔄 Refresh Videos</a>
            <a href="/api/refresh_articles" class="button">🔄 Refresh Articles</a>
            
            <h2>Video Perspectives</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Progressive</h3>
                    <div class="stat-number">{video_perspectives.get('progressive', 0)}</div>
                </div>
                <div class="stat-card">
                    <h3>Centrist</h3>
                    <div class="stat-number">{video_perspectives.get('centrist', 0)}</div>
                </div>
                <div class="stat-card">
                    <h3>Conservative</h3>
                    <div class="stat-number">{video_perspectives.get('conservative', 0)}</div>
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
        </div>
    </body>
    </html>
    '''
    
    conn.close()
    return html

@app.route('/api/refresh_videos')
def refresh_videos():
    count = refresh_video_database()
    return f"✅ Added {count} new videos. <a href='/admin'>Back to Admin</a>"

@app.route('/api/refresh_articles')
def refresh_articles():
    count = refresh_article_database()
    return f"✅ Added {count} new articles. <a href='/admin'>Back to Admin</a>"

# ==================== HTML TEMPLATES ====================
HOME_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>PolitiScope Research</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
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
        h1 { color: #333; margin-bottom: 10px; }
        .btn {
            background: #667eea; color: white; border: none;
            padding: 18px; border-radius: 12px; font-size: 1.1em;
            cursor: pointer; width: 100%; margin: 10px 0;
        }
        .btn:hover { background: #5a6fd8; }
        .btn-secondary { background: #764ba2; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 PolitiScope</h1>
        <p>Real Videos • Long-Form Articles • Research Study</p>
        
        <button class="btn" onclick="register()">🆕 New Participant</button>
        <button class="btn btn-secondary" onclick="login()">🔑 Returning</button>
        
        <p style="margin-top: 20px;"><a href="/admin">Admin Dashboard</a></p>
    </div>
    
    <script>
        async function register() {
            const res = await fetch('/register', { method: 'POST' });
            const data = await res.json();
            alert(`✅ Your ID: ${data.user_id}`);
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
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: {{ '#000' if theme == 'dark' else '#f5f5f5' }};
            color: {{ '#fff' if theme == 'dark' else '#333' }};
            padding: 20px;
        }
        .header {
            position: sticky; top: 0;
            background: {{ '#000' if theme == 'dark' else '#f5f5f5' }};
            padding: 15px; border-bottom: 1px solid #ddd;
            display: flex; justify-content: space-between;
            z-index: 100;
        }
        .feed-container { max-width: 800px; margin: 20px auto; }
        
        /* Video Card */
        .video-card, .article-card {
            background: {{ '#1a1a1a' if theme == 'dark' else 'white' }};
            border-radius: 15px; padding: 20px; margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border-left: 6px solid;
        }
        .progressive { border-left-color: #ff6b6b; }
        .centrist { border-left-color: #4ecdc4; }
        .conservative { border-left-color: #45b7d1; }
        
        .video-container {
            position: relative; width: 100%; margin: 15px 0;
        }
        .video-container iframe {
            width: 100%; height: 400px; border-radius: 10px;
        }
        
        .article-content {
            line-height: 1.8; font-size: 1.1em;
            max-height: 500px; overflow-y: auto;
            margin: 15px 0; padding: 15px;
            background: {{ 'rgba(255,255,255,0.02)' if theme == 'dark' else 'rgba(0,0,0,0.02)' }};
            border-radius: 10px;
        }
        
        .badge {
            display: inline-block; padding: 5px 12px;
            border-radius: 20px; font-size: 12px; font-weight: bold;
            margin-right: 10px;
        }
        .badge-progressive { background: #ff6b6b20; color: #ff6b6b; }
        .badge-centrist { background: #4ecdc420; color: #4ecdc4; }
        .badge-conservative { background: #45b7d120; color: #45b7d1; }
        
        .stats {
            display: flex; gap: 20px; margin: 10px 0;
            color: #888; font-size: 14px;
        }
        
        .buttons {
            display: flex; gap: 10px; margin-top: 15px;
        }
        .btn {
            flex: 1; padding: 12px; border: none; border-radius: 10px;
            cursor: pointer; font-weight: bold; color: white;
        }
        .btn-interested { background: #3498db; }
        .btn-informative { background: #2ecc71; }
        .btn-not-useful { background: #e74c3c; }
        
        .theme-toggle {
            position: fixed; bottom: 20px; right: 20px;
            background: {{ '#333' if theme == 'dark' else '#f0f0f0' }};
            color: {{ '#fff' if theme == 'dark' else '#333' }};
            border: none; padding: 12px 25px; border-radius: 30px;
            cursor: pointer; z-index: 1000;
        }
        .exit-btn {
            position: fixed; top: 20px; right: 20px;
            background: #e74c3c; color: white;
            border: none; padding: 8px 20px; border-radius: 20px;
            cursor: pointer; z-index: 1000;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>ID: <span class="user-id">{{ user_id }}</span></div>
        <div id="timer">00:00</div>
    </div>
    
    <div class="feed-container" id="feed"></div>
    <div id="loading" style="text-align: center; padding: 20px;">Loading...</div>
    
    <button class="theme-toggle" onclick="toggleTheme()">
        {{ '☀️ Light' if theme == 'dark' else '🌙 Dark' }}
    </button>
    <button class="exit-btn" onclick="window.location.href='/'">✕ Exit</button>
    
    <script>
        const userId = '{{ user_id }}';
        const condition = '{{ condition }}';
        const initialBatch = {{ initial_batch | safe }};
        
        let allItems = [...initialBatch];
        let seenIds = {videos: [], articles: []};
        let startTime = Date.now();
        let expandTimes = {};
        
        function renderFeed() {
            const feed = document.getElementById('feed');
            feed.innerHTML = '';
            
            allItems.forEach(item => {
                if (item.type === 'video') {
                    feed.appendChild(createVideoCard(item.data));
                } else {
                    feed.appendChild(createArticleCard(item.data));
                }
            });
        }
        
        function createVideoCard(video) {
            const card = document.createElement('div');
            card.className = `video-card ${video.perspective}`;
            card.innerHTML = `
                <div>
                    <span class="badge badge-${video.perspective}">🎬 ${video.perspective.toUpperCase()}</span>
                    <span>📺 ${video.channel_name}</span>
                    <h2>${video.title}</h2>
                    <p>${video.description.substring(0, 200)}...</p>
                    
                    <div class="video-container">
                        <iframe src="${video.embed_url}" frameborder="0" allowfullscreen></iframe>
                    </div>
                    
                    <div class="stats">
                        <span>👁️ ${video.view_count?.toLocaleString() || 'N/A'} views</span>
                        <span>👍 ${video.like_count?.toLocaleString() || 'N/A'} likes</span>
                        <span>💬 ${video.comment_count?.toLocaleString() || 'N/A'} comments</span>
                    </div>
                </div>
                
                <div class="buttons">
                    <button class="btn btn-interested" onclick="markInterested('video', ${video.id})">🔖 Interested</button>
                    <button class="btn btn-informative" onclick="rateContent('video', ${video.id}, 'informative')">✅ Informative</button>
                    <button class="btn btn-not-useful" onclick="rateContent('video', ${video.id}, 'not_useful')">❌ Not Useful</button>
                </div>
            `;
            return card;
        }
        
        function createArticleCard(article) {
            const card = document.createElement('div');
            card.className = `article-card ${article.perspective}`;
            
            // Parse word count
            const wordCount = article.word_count || article.content.split(' ').length;
            const readTime = Math.ceil(wordCount / 200);
            
            card.innerHTML = `
                <div>
                    <span class="badge badge-${article.perspective}">📰 ${article.perspective.toUpperCase()}</span>
                    <span>📝 ${article.source_name}</span>
                    <h2>${article.title}</h2>
                    
                    <div class="stats">
                        <span>📖 ${wordCount} words</span>
                        <span>⏱️ ${readTime} min read</span>
                        <span>✍️ ${article.author || 'Unknown'}</span>
                    </div>
                    
                    <div class="article-content">
                        ${article.content}
                    </div>
                    
                    <p><a href="${article.source_url}" target="_blank">🔗 Read original at ${article.source_name}</a></p>
                </div>
                
                <div class="buttons">
                    <button class="btn btn-interested" onclick="markInterested('article', ${article.id})">🔖 Interested</button>
                    <button class="btn btn-informative" onclick="rateContent('article', ${article.id}, 'informative')">✅ Informative</button>
                    <button class="btn btn-not-useful" onclick="rateContent('article', ${article.id}, 'not_useful')">❌ Not Useful</button>
                </div>
            `;
            return card;
        }
        
        async function loadMore() {
            const res = await fetch('/api/load_more', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({seen_ids: seenIds})
            });
            const data = await res.json();
            
            data.items.forEach(item => {
                allItems.push(item);
                if (item.type === 'video') {
                    seenIds.videos.push(item.data.id);
                } else {
                    seenIds.articles.push(item.data.id);
                }
            });
            
            renderFeed();
        }
        
        function markInterested(type, id) {
            fetch('/api/log_interaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content_id: id,
                    content_type: type,
                    action: 'interested'
                })
            });
            alert('✅ Interest recorded');
        }
        
        function rateContent(type, id, rating) {
            fetch('/api/log_interaction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    content_id: id,
                    content_type: type,
                    action: 'rate',
                    rating: rating
                })
            });
            alert(rating === 'informative' ? '✅ Rated informative' : '❌ Rated not useful');
        }
        
        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            document.getElementById('timer').textContent = `${mins.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}`;
        }
        
        async function toggleTheme() {
            const theme = document.body.style.background === 'rgb(0, 0, 0)' ? 'light' : 'dark';
            await fetch('/api/set_theme', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({theme: theme})
            });
            location.reload();
        }
        
        // Initialize
        renderFeed();
        setInterval(updateTimer, 1000);
        
        // Infinite scroll
        window.addEventListener('scroll', () => {
            if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 1000) {
                loadMore();
            }
        });
    </script>
</body>
</html>
'''

# ==================== INITIAL DATA LOAD ====================
with app.app_context():
    # Check if we need initial data
    conn = sqlite3.connect('politiscope.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM articles')
    article_count = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM videos')
    video_count = c.fetchone()[0]
    conn.close()
    
    if article_count == 0:
        print("📰 Initial article load...")
        refresh_article_database()
    
    if video_count == 0:
        print("📹 Initial video load...")
        refresh_video_database()

# ==================== RUN APPLICATION ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
