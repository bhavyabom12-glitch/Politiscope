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

# ==================== EXPANDED CONTENT DATABASE ====================
# 24 pieces of content (8 per perspective)
CONTENT = [
    # PROGRESSIVE (8 items)
    {
        "id": "p1", "type": "article", "perspective": "progressive",
        "title": "Medicare for All Explained",
        "summary": "How a single-payer system would work",
        "content": "A single-payer system would consolidate healthcare financing into one public agency. Proponents argue this reduces administrative overhead and ensures medical care as a human right regardless of income. The Congressional Budget Office estimates this would cover all Americans while eliminating premiums and deductibles.",
        "facts": ["Covers all Americans", "Eliminates premiums/deductibles", "Estimated 30M currently uninsured"],
        "source": "CBO Report 2024", "duration": 45,
        "image_url": "https://images.unsplash.com/photo-1505751172177-51ad18e739da?w=800"
    },
    {
        "id": "p2", "type": "video", "perspective": "progressive",
        "title": "Green New Deal Overview",
        "summary": "Climate action and jobs",
        "content": "This resolution calls for a 10-year national mobilization to achieve 100% clean energy by 2035, create 10 million jobs, and guarantee economic security for all Americans. Includes massive investments in wind, solar, and battery storage.",
        "facts": ["$2T investment", "100% clean energy by 2035", "10M jobs created"],
        "source": "Sunrise Movement", "duration": 50,
        "image_url": "https://images.unsplash.com/photo-1466611653911-954815391f27?w=800"
    },
    {
        "id": "p3", "type": "article", "perspective": "progressive",
        "title": "Wealth Tax Proposal",
        "summary": "Taxing extreme wealth",
        "content": "The wealth tax would apply an annual 2% tax on net worth above $50 million. Proponents estimate this could raise $3 trillion over a decade from just the top 0.1% of households. The policy aims to address growing wealth concentration and fund social programs.",
        "facts": ["Top 0.1% affected", "$3T revenue estimate", "Closes loopholes"],
        "source": "ProPublica", "duration": 40,
        "image_url": "https://images.unsplash.com/photo-1565379488613-5850c844ef58?w=800"
    },
    {
        "id": "p4", "type": "infographic", "perspective": "progressive",
        "title": "Pathway to Citizenship",
        "summary": "Immigration reform proposal",
        "content": "The proposal would create an 8-year pathway to citizenship for approximately 11 million undocumented immigrants, with special provisions for 3.6 million Dreamers brought to the country as children. Economic analysis suggests this would add $1.2 trillion to GDP over the next decade.",
        "facts": ["Affects 11M people", "+$1.2T to GDP", "3.6M Dreamers eligible"],
        "source": "Center for American Progress", "duration": 55,
        "image_url": "https://images.unsplash.com/photo-1501901609772-df0848060b33?w=800"
    },
    {
        "id": "p5", "type": "article", "perspective": "progressive",
        "title": "Student Debt Forgiveness",
        "summary": "Economic relief for borrowers",
        "content": "Proposals to cancel student debt range from $10,000 to $50,000 per borrower. Supporters argue this would boost the economy by allowing younger generations to buy homes and start businesses. Critics worry about the cost and fairness to those who already paid.",
        "facts": ["45M borrowers", "$1.7T total debt", "Average debt: $37K"],
        "source": "Education Data Initiative", "duration": 35,
        "image_url": "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800"
    },
    {
        "id": "p6", "type": "video", "perspective": "progressive",
        "title": "Paid Family Leave",
        "summary": "Support for working families",
        "content": "The FAMILY Act would create a national paid family and medical leave program, providing up to 12 weeks of partial income. The US is one of the few countries without federal paid leave. Studies show benefits for child development and maternal health.",
        "facts": ["12 weeks leave", "66% wage replacement", "Covers 100M workers"],
        "source": "Department of Labor", "duration": 40,
        "image_url": "https://images.unsplash.com/photo-1544027993-37dbfe4430b7?w=800"
    },
    {
        "id": "p7", "type": "article", "perspective": "progressive",
        "title": "Voting Rights Act",
        "summary": "Protecting democracy",
        "content": "The John Lewis Voting Rights Act would restore key provisions of the 1965 Voting Rights Act, requiring federal approval for voting changes in states with histories of discrimination. Supporters say it's needed to combat voter suppression.",
        "facts": ["Restores Section 5", "Covers 9 states", "Bipartisan support in 2006"],
        "source": "Brennan Center", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?w=800"
    },
    {
        "id": "p8", "type": "infographic", "perspective": "progressive",
        "title": "Minimum Wage Increase",
        "summary": "$15 by 2025",
        "content": "The Raise the Wage Act would gradually increase the federal minimum wage to $15 per hour by 2025. The current $7.25 rate hasn't increased since 2009. Studies show mixed effects on employment but significant poverty reduction.",
        "facts": ["27M workers affected", "Lifts 900K from poverty", "$15 by 2025"],
        "source": "Economic Policy Institute", "duration": 25,
        "image_url": "https://images.unsplash.com/photo-1554224154-26032ffc0d07?w=800"
    },
    
    # CENTRIST (8 items)
    {
        "id": "c1", "type": "article", "perspective": "centrist",
        "title": "The Public Option Compromise",
        "summary": "Middle ground on healthcare",
        "content": "A public option would create a government-run insurance plan that competes with private insurers, giving consumers choice while expanding coverage. This compromise aims to achieve near-universal coverage without completely displacing the private market.",
        "facts": ["$1.5T cost estimate", "88% coverage target", "Preserves private insurance option"],
        "source": "Brookings Institute", "duration": 25,
        "image_url": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=800"
    },
    {
        "id": "c2", "type": "infographic", "perspective": "centrist",
        "title": "Climate Resilience Plan",
        "summary": "Balanced climate policy",
        "content": "This middle-ground approach pairs carbon pricing with investments in climate adaptation infrastructure. The plan would set a 2050 net-zero target while providing funding for coastal resilience and flood control. Carbon pricing would start low and gradually increase.",
        "facts": ["$300B for infrastructure", "Carbon pricing included", "2050 net-zero target"],
        "source": "BPC Analysis", "duration": 35,
        "image_url": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=800"
    },
    {
        "id": "c3", "type": "article", "perspective": "centrist",
        "title": "Balanced Budget Plan",
        "summary": "Fiscal responsibility",
        "content": "This plan combines targeted spending cuts with revenue increases to stabilize the debt-to-GDP ratio over a 10-year window. Includes Medicare drug price negotiation, a 28% corporate rate, and caps on discretionary spending.",
        "facts": ["10-year timeline", "Spending cuts + revenue", "Debt stabilization"],
        "source": "CRFB Report", "duration": 40,
        "image_url": "https://images.unsplash.com/photo-1543286386-2e659306cd6c?w=800"
    },
    {
        "id": "c4", "type": "video", "perspective": "centrist",
        "title": "Bipartisan Immigration Deal",
        "summary": "Compromise on immigration",
        "content": "The compromise pairs $20 billion in border security funding with a 5-year pathway to citizenship for approximately 2 million Dreamers. It would also create a new visa program for essential workers and modernize the legal immigration system.",
        "facts": ["$20B for security", "2M Dreamers covered", "5-year pathway"],
        "source": "Bipartisan Policy Center", "duration": 45,
        "image_url": "https://images.unsplash.com/photo-1581291518633-83b4ebd1d83e?w=800"
    },
    {
        "id": "c5", "type": "article", "perspective": "centrist",
        "title": "Infrastructure Investment",
        "summary": "Bipartisan infrastructure deal",
        "content": "The $1.2 trillion infrastructure bill funds roads, bridges, public transit, rail, broadband, and water systems. It represents a compromise between progressive spending goals and conservative fiscal concerns.",
        "facts": ["$1.2T total", "$550B new spending", "5-year plan"],
        "source": "Congressional Budget Office", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1513828583688-c52646db42da?w=800"
    },
    {
        "id": "c6", "type": "infographic", "perspective": "centrist",
        "title": "Gun Safety Compromise",
        "summary": "Moderate gun reforms",
        "content": "The Bipartisan Safer Communities Act enhanced background checks for buyers under 21, provided funding for red flag laws, and closed the boyfriend loophole. It represents the first major federal gun safety legislation in decades.",
        "facts": ["Enhanced checks", "$750M for crisis intervention", "Closes dating partner loophole"],
        "source": "Department of Justice", "duration": 25,
        "image_url": "https://images.unsplash.com/photo-1523995462485-3d171b5c8fa9?w=800"
    },
    {
        "id": "c7", "type": "article", "perspective": "centrist",
        "title": "Electoral Count Reform",
        "summary": "Fixing presidential election rules",
        "content": "The Electoral Count Reform Act clarifies the vice president's role is ministerial and raises the threshold for objecting to electors. It aims to prevent future attempts to overturn election results while preserving states' roles.",
        "facts": ["VP role clarified", "1/5 threshold for objections", "Bipartisan support"],
        "source": "Lawfare Institute", "duration": 35,
        "image_url": "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?w=800"
    },
    {
        "id": "c8", "type": "video", "perspective": "centrist",
        "title": "Tech Regulation",
        "summary": "Balancing innovation and privacy",
        "content": "Proposals for tech regulation aim to balance innovation with consumer protection. Ideas include federal privacy laws, Section 230 reforms, and antitrust enforcement. The challenge is maintaining US tech leadership while addressing concerns.",
        "facts": ["No federal privacy law", "Section 230 under review", "Big tech antitrust cases"],
        "source": "Brookings Tech", "duration": 40,
        "image_url": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800"
    },
    
    # CONSERVATIVE (8 items)
    {
        "id": "r1", "type": "article", "perspective": "conservative",
        "title": "Market-Based Healthcare Reform",
        "summary": "Competition and choice drive quality",
        "content": "Market-based reforms focus on deregulation and increasing competition between private insurers. This approach aims to lower costs through innovation, price transparency, and personal health savings accounts. Health Savings Accounts now cover over 30 million Americans.",
        "facts": ["$450B estimated savings", "Expands Health Savings Accounts", "HSAs cover 30M+ users"],
        "source": "Heritage Foundation", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1454165833006-cc331c71dd62?w=800"
    },
    {
        "id": "r2", "type": "article", "perspective": "conservative",
        "title": "Energy Innovation Approach",
        "summary": "Technology over regulation",
        "content": "This approach prioritizes technological innovation over government mandates, funding research into carbon capture, advanced nuclear reactors, and next-generation solar. The strategy includes tax credits for clean energy innovation and streamlining regulations for nuclear plant construction.",
        "facts": ["$500M for carbon capture", "Nuclear expansion", "R&D tax credits"],
        "source": "AEI Report", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1513828583688-c52646db42da?w=800"
    },
    {
        "id": "r3", "type": "infographic", "perspective": "conservative",
        "title": "Tax Cuts & Growth",
        "summary": "Supply-side economics",
        "content": "The Tax Cuts and Jobs Act of 2017 lowered the corporate rate from 35% to 21%. Supporters credit this with increasing business investment and job creation. Treasury analysis showed repatriation of over $1 trillion in overseas profits following the reform.",
        "facts": ["21% corporate rate", "Job growth focus", "Deregulation agenda"],
        "source": "Tax Foundation", "duration": 35,
        "image_url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800"
    },
    {
        "id": "r4", "type": "video", "perspective": "conservative",
        "title": "Border Security First",
        "summary": "Secure borders before reform",
        "content": "This approach insists that border security must be achieved before any legalization program begins. Current proposals include hiring 20,000 additional border patrol agents, completing 500 miles of physical barriers, and implementing mandatory E-Verify nationwide.",
        "facts": ["1.7M 2023 encounters", "20K more agents proposed", "Technology upgrades funded"],
        "source": "DHS Report", "duration": 40,
        "image_url": "https://images.unsplash.com/photo-1444210971048-6130cf0c46cf?w=800"
    },
    {
        "id": "r5", "type": "article", "perspective": "conservative",
        "title": "School Choice",
        "summary": "Education freedom",
        "content": "School choice programs allow parents to use public education funds for private schools, charter schools, or homeschooling. Supporters argue competition improves education quality. Opponents worry about draining resources from public schools.",
        "facts": ["32 states have choice programs", "700K voucher students", "Avg voucher: $4,900"],
        "source": "EdChoice", "duration": 30,
        "image_url": "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800"
    },
    {
        "id": "r6", "type": "infographic", "perspective": "conservative",
        "title": "Second Amendment Rights",
        "summary": "Constitutional carry and self-defense",
        "content": "Constitutional carry laws allow citizens to carry concealed firearms without a permit. Currently 27 states have permitless carry. Supporters cite self-defense rights and the Second Amendment. Opponents point to public safety concerns.",
        "facts": ["27 states constitutional carry", "22M NICS checks (2023)", "Self-defense use: 500K/year"],
        "source": "NRA-ILA", "duration": 25,
        "image_url": "https://images.unsplash.com/photo-1523995462485-3d171b5c8fa9?w=800"
    },
    {
        "id": "r7", "type": "article", "perspective": "conservative",
        "title": "Federalism and States' Rights",
        "summary": "Limiting federal power",
        "content": "The principle of federalism reserves powers not delegated to the federal government to the states. Recent Supreme Court cases have reinforced state authority on issues from abortion to environmental regulation. This allows policy experimentation at the state level.",
        "facts": ["10th Amendment", "Federal vs state powers", "Laboratory of democracy"],
        "source": "Federalist Society", "duration": 35,
        "image_url": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=800"
    },
    {
        "id": "r8", "type": "video", "perspective": "conservative",
        "title": "Free Speech on Campus",
        "summary": "Protecting academic freedom",
        "content": "Concerns about free speech on college campuses have led to legislative efforts to protect diverse viewpoints. Proponents argue intellectual diversity is essential for education. Critics worry about protecting hate speech and harassment.",
        "facts": ["36 states considering campus speech bills", "First Amendment protections", "Viewpoint diversity"],
        "source": "FIRE", "duration": 40,
        "image_url": "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?w=800"
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

def generate_content_batch(condition, user_id, count=5):
    """Generate a batch of content based on condition and user history"""
    if condition == 'normal':
        # FILTER BUBBLE: Weight toward preferred perspective
        # Get user's interaction history
        conn = get_db()
        c = conn.cursor()
        c.execute('''SELECT perspective, COUNT(*) as cnt 
                     FROM interactions 
                     WHERE user_id = ? AND action IN ('view', 'interested', 'rate_informative')
                     GROUP BY perspective''', (user_id,))
        history = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        
        # If no history, start with random preference
        if not history:
            fav = random.choice(['progressive', 'centrist', 'conservative'])
        else:
            fav = max(history, key=history.get)
        
        # 70% from favorite perspective, 30% random
        batch = []
        for i in range(count):
            if i < int(count * 0.7):  # 70% favorite
                fav_items = [c for c in CONTENT if c['perspective'] == fav]
                batch.append(random.choice(fav_items))
            else:  # 30% other perspectives
                other_items = [c for c in CONTENT if c['perspective'] != fav]
                batch.append(random.choice(other_items))
    else:
        # DIVERSE: Balanced perspectives
        perspectives = ['progressive', 'centrist', 'conservative']
        batch = []
        for i in range(count):
            p = random.choice(perspectives)
            items = [c for c in CONTENT if c['perspective'] == p]
            batch.append(random.choice(items))
    
    random.shuffle(batch)
    return batch

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
    
    # Get initial batch
    initial_batch = generate_content_batch(condition, user_id, 5)
    
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
                                 initial_batch=json.dumps([{
                                     'id': item['id'],
                                     'type': item['type'],
                                     'perspective': item['perspective'],
                                     'title': item['title'],
                                     'summary': item['summary'],
                                     'content': item['content'],
                                     'facts': item['facts'],
                                     'source': item['source'],
                                     'duration': item['duration'],
                                     'image_url': item['image_url']
                                 } for item in initial_batch]))

@app.route('/api/load_more', methods=['POST'])
@login_required
def load_more():
    """API endpoint to load more content (infinite scroll)"""
    data = request.json
    user_id = session['user_id']
    condition = session['condition']
    current_ids = data.get('current_ids', [])
    
    # Generate new batch
    new_batch = generate_content_batch(condition, user_id, 3)
    
    # Filter out duplicates (though our generator should handle this)
    new_items = [item for item in new_batch if item['id'] not in current_ids]
    
    return jsonify({
        'items': [{
            'id': item['id'],
            'type': item['type'],
            'perspective': item['perspective'],
            'title': item['title'],
            'summary': item['summary'],
            'content': item['content'],
            'facts': item['facts'],
            'source': item['source'],
            'duration': item['duration'],
            'image_url': item['image_url']
        } for item in new_items]
    })

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
    <title>Politiscope Research Study</title>
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
        <h1>📊 Politiscope </h1>
        <p class="subtitle">A 2026 AP Research Study on Political Perspectives</p>
        
        <div class="btn-container">
            <button class="btn" onclick="register()">Register New Account</button>
            <button class="btn btn-secondary" onclick="login()">Returning User</button>
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
        .loading {
            text-align: center;
            padding: 20px;
            color: #888;
        }
        .infinite-scroll-trigger {
            height: 20px;
            margin: 20px 0;
            text-align: center;
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
        <div class="target-time">Target: 20 minutes • Scroll for endless content</div>
    </div>
    
    <div class="feed-container" id="feed"></div>
    <div class="infinite-scroll-trigger" id="scrollTrigger"></div>
    <div class="loading" id="loading" style="display: none;">Loading more content...</div>
    
    <button class="theme-toggle" onclick="toggleTheme()">
        {{ '☀️ Light' if theme == 'dark' else '🌙 Dark' }}
    </button>
    
    <button class="exit-btn" onclick="exitSession()">✕ Exit</button>
    
    <script>
        const userId = '{{ user_id }}';
        const condition = '{{ condition }}';
        const initialBatch = {{ initial_batch | safe }};
        
        let allItems = [...initialBatch];
        let loadedIds = new Set(initialBatch.map(item => item.id));
        let startTime = Date.now();
        let expandTimes = {};
        let cardStartTimes = {};
        let isLoading = false;
        let hasMore = true;
        
        console.log('🔬 Research condition for user', userId + ':', condition);
        console.log('Initial feed loaded with', allItems.length, 'items');
        
        // Render feed
        function renderFeed() {
            const feed = document.getElementById('feed');
            if (!feed) return;
            
            feed.innerHTML = '';
            allItems.forEach((item, index) => {
                const card = createCard(item, index);
                feed.appendChild(card);
            });
            
            // Setup intersection observer for infinite scroll
            setupInfiniteScroll();
        }
        
        function createCard(item, index) {
            const card = document.createElement('div');
            card.className = `content-card ${item.perspective}`;
            card.dataset.contentId = item.id;
            card.dataset.index = index;
            
            const typeEmoji = item.type === 'video' ? '🎬' : item.type === 'article' ? '📰' : '📊';
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
        
        // Infinite scroll setup
        function setupInfiniteScroll() {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting && !isLoading && hasMore) {
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
            if (isLoading || !hasMore) return;
            
            isLoading = true;
            document.getElementById('loading').style.display = 'block';
            
            try {
                const res = await fetch('/api/load_more', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        current_ids: Array.from(loadedIds)
                    })
                });
                
                const data = await res.json();
                
                if (data.items && data.items.length > 0) {
                    // Add new items
                    data.items.forEach(item => {
                        if (!loadedIds.has(item.id)) {
                            allItems.push(item);
                            loadedIds.add(item.id);
                        }
                    });
                    
                    // Re-render feed with new items
                    renderFeed();
                } else {
                    hasMore = false;
                }
            } catch (error) {
                console.error('Error loading more content:', error);
            } finally {
                isLoading = false;
                document.getElementById('loading').style.display = 'none';
            }
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
        
        // Timer and progress
        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            const timeString = `${mins.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}`;
            
            document.getElementById('timer').textContent = timeString;
            document.getElementById('bigTimer').textContent = timeString;
            
            // Progress toward 20 minutes (1200 seconds)
            const progress = Math.min((elapsed / 1200) * 100, 100);
            document.getElementById('progressFill').style.width = progress + '%';
        }
        
        // Exit session
        function exitSession() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            
            if (confirm(`You spent ${mins}:${secs.toString().padStart(2,'0')} minutes today.\n\nExit to homepage?`)) {
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

@app.route('/admin')
def admin():
    """Admin dashboard - shows research stats"""
    conn = get_db()
    c = conn.cursor()
    
    # Get statistics
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT condition, COUNT(*) FROM users GROUP BY condition")
    condition_counts = dict(c.fetchall())
    
    c.execute("SELECT COUNT(*) FROM interactions")
    total_interactions = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM interactions WHERE action LIKE '%expand%'")
    total_expands = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM interactions WHERE action = 'interested'")
    total_interested = c.fetchone()[0]
    
    c.execute('''SELECT perspective, COUNT(*) FROM interactions GROUP BY perspective''')
    perspective_counts = dict(c.fetchall())
    
    c.execute('''SELECT action, COUNT(*) FROM interactions GROUP BY action''')
    action_counts = dict(c.fetchall())
    
    # Get recent interactions
    c.execute('''SELECT user_id, timestamp, perspective, action, rating 
                 FROM interactions ORDER BY timestamp DESC LIMIT 20''')
    recent = c.fetchall()
    
    conn.close()
    
    # Simple HTML admin dashboard
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PolitiScope Admin</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .stat-card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #333; }}
            table {{ width: 100%; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔬 PolitiScope Admin Dashboard</h1>
                <p>Research Data - Condition hidden from users</p>
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
                    <h3>Total Interactions</h3>
                    <div class="stat-number">{total_interactions}</div>
                </div>
                <div class="stat-card">
                    <h3>Expands</h3>
                    <div class="stat-number">{total_expands}</div>
                </div>
                <div class="stat-card">
                    <h3>Interested</h3>
                    <div class="stat-number">{total_interested}</div>
                </div>
            </div>
            
            <h2>Recent Activity</h2>
            <table>
                <tr>
                    <th>User ID</th>
                    <th>Time</th>
                    <th>Perspective</th>
                    <th>Action</th>
                    <th>Rating</th>
                </tr>
                {"".join(f"<tr><td>{r[0]}</td><td>{r[1][:19]}</td><td>{r[2] or '—'}</td><td>{r[3]}</td><td>{r[4] or '—'}</td></tr>" for r in recent)}
            </table>
        </div>
    </body>
    </html>
    '''
    
    return html

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
