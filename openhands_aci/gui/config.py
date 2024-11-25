from .typing import Resolution

# Scaling to these targets to avoid automatic scaling
# by the API.
MAX_SCALING_TARGETS: dict[str, Resolution] = {
    'XGA': Resolution(width=1024, height=768),  # 4:3
    'WXGA': Resolution(width=1280, height=800),  # 16:10
    'FWXGA': Resolution(width=1366, height=768),  # ~16:9
}

TYPING_DELAY_MS = 12
TYPING_CHUNK_SIZE = 50
