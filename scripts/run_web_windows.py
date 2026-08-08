"""Windows helper: start Flask web on 0.0.0.0:5001"""
from app import create_app

app = create_app()
app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
