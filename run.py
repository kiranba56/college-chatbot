import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import app
from config import Config

if __name__ == '__main__':
    print("=" * 60)
    print(f"🎓 {Config.COLLEGE_NAME} - AI Campus Assistant")
    print(f"🚀 Running at: http://127.0.0.1:{Config.PORT}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)

