from flask import Flask
from .like_routes import initialize_routes
from .token_manager import TokenCache

def create_app():
    app = Flask(__name__)

    # ✅ Multi gateway servers (fallback enabled)
    SERVERS = {
        "PK": [
            "https://clientbp.ggpolarbear.com",
            "https://clientbp.ggblueshark.com",
            "https://clientbp.ggshark.com",
            "https://clientbp.ggwhitehawk.com"
        ],
        "IND": [
            "https://clientbp.ggblueshark.com"
        ],
        "SG": [
            "https://clientbp.ggpolarbear.com"
        ]
    }

    # টোকেন ক্যাশ ইনিশিয়ালাইজ করা হলো
    token_cache = TokenCache()
    
    # টেস্টের জন্য ব্যাকগ্রাউন্ড রিফ্রেশ বন্ধ রাখা হয়েছে
    # token_cache.start_background_refresh() 

    # রাউটগুলো লোড করা হলো
    initialize_routes(app, SERVERS, token_cache)

    return app

# Vercel-এর জন্য মেইন অ্যাপ অবজেক্ট
app = create_app()