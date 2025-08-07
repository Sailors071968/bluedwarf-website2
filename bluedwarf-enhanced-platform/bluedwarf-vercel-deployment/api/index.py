import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import app

# This is the entry point for Vercel
def handler(request):
    return app(request.environ, lambda status, headers: None)

