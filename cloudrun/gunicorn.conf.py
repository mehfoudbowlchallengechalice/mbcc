"""One small instance; share the Sheets snapshot cache across request threads."""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8080")
workers = 1
worker_class = "gthread"
threads = 8
timeout = 60
accesslog = "-"
errorlog = "-"
capture_output = True

