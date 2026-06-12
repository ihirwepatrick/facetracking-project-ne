"""
Configuration module for face recognition pipeline.
Centralized settings for all modules.
"""

from pathlib import Path
from typing import Tuple

# ============================================================================
# PROJECT PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_DIR = DATA_DIR / "db"
ENROLL_DIR = DATA_DIR / "enroll"
DEBUG_ALIGNED_DIR = DATA_DIR / "debug_aligned"
MODELS_DIR = PROJECT_ROOT / "models"

# History directory for locked person activity logs
HISTORY_DIR = DATA_DIR / "history"
ACTIVITY_LOGS_DIR = HISTORY_DIR  # Alias for backward compatibility

# Database files
DB_NPZ_PATH = DB_DIR / "face_db.npz"
DB_JSON_PATH = DB_DIR / "face_db.json"

# ONNX / MediaPipe model paths
ARCFACE_MODEL_PATH = MODELS_DIR / "embedder_arcface.onnx"
FACE_LANDMARKER_MODEL_PATH = MODELS_DIR / "face_landmarker.task"

# ============================================================================
# FACE DETECTION SETTINGS
# ============================================================================

HAAR_CASCADE_PATH = None  # None = use OpenCV default haarcascade_frontalface_default.xml
HAAR_SCALE_FACTOR = 1.08  # Finer scan = more stable boxes (slightly slower)
HAAR_MIN_NEIGHBORS = 3
HAAR_MIN_SIZE = (45, 45)
DETECT_FRAME_SCALE = 0.85  # Slightly higher res for steadier landmarks
HAAR_FLAGS = None  # cv2.CASCADE_SCALE_IMAGE if needed

# ============================================================================
# 5-POINT LANDMARK DETECTION (MediaPipe FaceMesh)
# ============================================================================

LANDMARK_INDICES = {
    "left_eye": 33,
    "right_eye": 263,
    "nose_tip": 1,
    "mouth_left": 61,
    "mouth_right": 291,
}

FACEMESH_STATIC_MODE = False
FACEMESH_MAX_NUM_FACES = 3
FACEMESH_REFINE_LANDMARKS = False  # Off = much faster; still accurate for 5-pt align
FACEMESH_MIN_DETECTION_CONFIDENCE = 0.42
FACEMESH_MIN_TRACKING_CONFIDENCE = 0.42

# ============================================================================
# FACE ALIGNMENT SETTINGS
# ============================================================================

ALIGNMENT_OUTPUT_SIZE: Tuple[int, int] = (112, 112)  # Standard for ArcFace
ALIGNMENT_PAD_X = 0.55
ALIGNMENT_PAD_Y_TOP = 0.85
ALIGNMENT_PAD_Y_BOT = 1.15
MIN_EYE_DISTANCE = 8.0  # Pixels; sanity check for geometry

# ============================================================================
# ARCFACE EMBEDDING SETTINGS
# ============================================================================

EMBEDDING_INPUT_SIZE = (112, 112)
EMBEDDING_DIM = 512
EMBEDDING_NORM_EPSILON = 1e-12
ONNX_EXECUTION_PROVIDER = "CPUExecutionProvider"
ONNX_INTRA_OP_THREADS = 4  # Parallel CPU inference for ArcFace

# Preprocessing constants (standard for ArcFace/InsightFace)
EMBEDDING_PREPROCESS_MEAN = 127.5
EMBEDDING_PREPROCESS_SCALE = 128.0

# ============================================================================
# ENROLLMENT SETTINGS
# ============================================================================

SAMPLES_NEEDED_FOR_ENROLLMENT = 15
MIN_SAMPLES_TO_SAVE = 3
MAX_EXISTING_CROPS_PER_PERSON = 300
AUTO_CAPTURE_INTERVAL_SECONDS = 0.25
SAVE_ENROLLMENT_CROPS = True

# ============================================================================
# RECOGNITION & THRESHOLD SETTINGS
# ============================================================================

DEFAULT_DISTANCE_THRESHOLD = 0.52  # Cosine distance; lower = stricter / more accurate
SIMILARITY_THRESHOLD = 0.70  # 1 - distance_threshold (for reference)
TARGET_FAR = 0.01  # 1% False Accept Rate for threshold tuning
THRESHOLD_SWEEP_RANGE = (0.10, 1.20, 0.01)  # (start, end, step)

# Aliases for the canonical recognition tuning interface (Issue #7)
RECOGNITION_THRESHOLD = DEFAULT_DISTANCE_THRESHOLD  # Accept identity if dist <= this
FACE_MATCH_THRESHOLD = 0.55  # Looser gate used to keep an existing lock alive
MAX_FACES = 5  # Maximum simultaneous faces to detect/recognize
RECOGNITION_INTERVAL = 4
RECOGNITION_INTERVAL_LOCKED = 2
RECOGNITION_INTERVAL_FACE = 4  # Re-embed every N frames while face visible
RECOGNITION_INTERVAL_LOCKED_FACE = 1   # Re-embed locked track every frame for fastest re-lock
RECOGNITION_INTERVAL_IDLE = 20
RECOGNITION_COOLDOWN_FRAMES = 4
RECOGNITION_COOLDOWN_FRAMES_FACE = 3
RECOGNITION_STABILIZE_WINDOW = 5

# ============================================================================
# RECOGNITION PIPELINE OPTIMIZATION
# ============================================================================

PROCESS_EVERY_N_FRAMES = 2
PROCESS_EVERY_N_FRAMES_FACE = 2  # Detect + embed every 2nd frame when face present
PROCESS_EVERY_N_FRAMES_IDLE = 6  # Slow scan when no face
PROCESS_EVERY_N_FRAMES_TRACKING = 2
DETECT_EVERY_N_FRAMES_FACE = 1  # Detect every frame while tracking — fewer false "lost" events
DETECT_EVERY_N_FRAMES_IDLE = 4
FACE_CENTER_SMOOTHING = 0.22  # EMA on face X/Y — lower = smoother, less servo jitter
ACTION_DETECT_EVERY_N_FRAMES = 4  # Blink/smile less often
ROI_MARGIN_FACTOR = 0.25  # Expand ROI by this fraction of width/height
SMOOTHING_WINDOW = 5  # EMA smoothing for face center X
ACCEPT_HOLD_FRAMES = 10  # Keep boxes/labels alive between skipped frames
MAX_FACES_TO_PROCESS = 2  # Cap embed cost in crowded scenes
LOCK_CONFIDENCE_MAX_DISTANCE = 0.45  # Maintain lock while distance <= this
LOCK_RELEASE_DISTANCE = 0.58 # Drop lock if distance exceeds this

# ============================================================================
# CAMERA SETTINGS
# ============================================================================

CAMERA_INDEX = 0  # Use python -m src.camera_utils to find the right index
CAMERA_AUTO_DETECT = True  # Fall back to other indices if CAMERA_INDEX fails
CAMERA_FRAME_WIDTH = 640
CAMERA_FRAME_HEIGHT = 480
CAMERA_FPS_TARGET = 30
CAMERA_OPEN_VERIFY_FRAMES = 5  # Test reads when opening
CAMERA_READ_RETRIES = 5  # Per-frame read attempts before counting a failure
CAMERA_RECONNECT_AFTER_FAILS = 3  # Consecutive bad reads before reconnect
CAMERA_RECONNECT_DELAY_SEC = 0.35  # Pause before reopening the device

# ============================================================================
# DISPLAY SETTINGS
# ============================================================================

DISPLAY_FPS = True
DISPLAY_CONFIDENCE = True
DISPLAY_LANDMARKS = False  # Off = faster overlay drawing
DISPLAY_ALIGNED_PREVIEW = False
PREVIEW_THUMB_SIZE = 112
DISPLAY_WINDOW_WIDTH = 800
DISPLAY_WINDOW_HEIGHT = 450

# Font settings for OpenCV text rendering
FONT_FACE = 2  # cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.7
FONT_THICKNESS = 2
FONT_COLOR_OK = (0, 255, 0)  # Green (BGR)
FONT_COLOR_REJECT = (0, 0, 255)  # Red (BGR)
FONT_COLOR_TEXT = (255, 255, 255)  # White (BGR)

# ============================================================================
# FACE LOCKING (Term-02 Week-04)
# ============================================================================

LOCK_RELEASE_FRAMES = 45
LOCK_MOVEMENT_THRESHOLD_PX = 25
LOCK_EAR_BLINK_THRESHOLD = 0.22
LOCK_SMILE_MOUTH_RATIO = 1.18
LOCK_ACTION_COOLDOWN_FRAMES = 10
LOCK_EAR_LEFT_INDICES = (33, 160, 158, 133, 153, 144)
LOCK_EAR_RIGHT_INDICES = (362, 385, 387, 263, 373, 380)
LOCK_MOUTH_LEFT_INDEX = 61
LOCK_MOUTH_RIGHT_INDEX = 291

# ============================================================================
# MQTT CAMERA TRACKING SETTINGS
# ============================================================================

# MQTT Broker settings
MQTT_BROKER_HOST = "192.168.8.105"  # Your PC LAN IP (ipconfig); ESP8266 must reach same broker
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = None  # Optional: Set if broker requires authentication
MQTT_PASSWORD = None  # Optional: Set if broker requires authentication

# MQTT Topics
MQTT_TOPIC_HORIZONTAL = "camera/track/horizontal"
MQTT_TOPIC_COMMAND = "camera/track/command"
MQTT_TOPIC_STATUS = "camera/status"
MQTT_KEEPALIVE = 30
MQTT_QOS = 1
MQTT_MIN_COMMAND_INTERVAL_MS = 50  # Throttle commands — prevents ESP target pile-up
MQTT_SEARCH_COMMAND_INTERVAL_MS = 250  # One search command at a time
SERVO_MIN_COMMAND_DELTA = 1  # Ignore duplicate degree commands
ESP_STATUS_TIMEOUT_SEC = 4.0  # No status this long = treat ESP as offline

# ----------------------------------------------------------------------------
# SERVO CONTROL (must match ESP8266 firmware limits)
# ----------------------------------------------------------------------------
SERVO_MIN_ANGLE = 0    # Full pan range for tracking + search
SERVO_MAX_ANGLE = 180
SERVO_CENTER_ANGLE = 90
# Canonical aliases (Issue #7 "servo:" group)
MIN_ANGLE = SERVO_MIN_ANGLE
MAX_ANGLE = SERVO_MAX_ANGLE
CENTER_ANGLE = SERVO_CENTER_ANGLE

# Mounting sign: +1 if increasing angle pans the camera toward image-right,
# -1 if it pans toward image-left. Flip this if the camera chases the wrong way.
SERVO_DIRECTION_SIGN = 1

# PID-style pan controller (operates on normalized horizontal error in [-1, 1])
SERVO_PID_KP = 22.0   # Follow locked face toward frame center
SERVO_PID_KI = 0.0    # Integral gain (kept 0 by default to avoid windup)
SERVO_PID_KD = 5.0    # Damping while following
SERVO_PID_I_CLAMP = 8.0  # Max absolute integral contribution (deg)

# Rate limiting / smoothing
SERVO_MAX_SPEED = 14     # Max deg/frame while following locked person
MAX_SPEED = SERVO_MAX_SPEED  # Alias (Issue #7)
SMOOTHING_FACTOR = 0.78   # EMA on face horizontal error
SERVO_OUTPUT_SMOOTHING = 0.38  # Smooth pan commands while following
SERVO_STEP_SIZE = 8      # Manual nudge step (left/right keys, command mode)
SERVO_MAX_PAN_OFFSET = 90  # Max degrees from center when tracking

# Dead zone: servo holds only when face is within this many pixels of frame center.
CENTER_DEAD_ZONE = 36  # Hold still when face is within this many px of center
SERVO_DEAD_ZONE_NORMALIZED = 0.06  # Legacy normalized fallback

# ----------------------------------------------------------------------------
# TRACKING BEHAVIOR
# ----------------------------------------------------------------------------
ENABLE_AUTO_CENTERING = False
LOCK_HOLD_SERVO = True      # When locked person is visible: servo holds still (no pan)
LOCK_FOLLOW_CENTER = False  # Disabled — no auto-centering while locked
CENTERING_TOLERANCE = 0.07    # Normalized half-width counted as "centered"
FRAMES_TO_LOCK_CENTER = 4     # Frames in center zone before LOCKED state

# Legacy step-based mode (kept for compatibility; PID path is preferred)
MOVEMENT_BASED_TRACKING = False
MOVEMENT_SENSITIVITY = 25
TRACKING_MOVEMENT_THRESHOLD = 0.05

# ----------------------------------------------------------------------------
# LOST-TARGET SEARCH & REACQUISITION (Issues #4, #5)
# ----------------------------------------------------------------------------
TRACKING_STARTUP_GRACE_SEC = 5.0   # After lock selected: no search until camera warms up
LOST_TARGET_TIMEOUT = 3.0        # Grace before search — fewer false sweeps
LOST_TARGET_FRAMES = 30          # Keep track alive through brief detection gaps
# If locked track stays visible but is unrecognized for this long → treat as lost
LOST_TARGET_UNRECOGNIZED_SEC = 4.0

# Search sweep — slow full ping-pong 0° → 180° → 0° until person reappears
SEARCH_MIN_ANGLE = 0
SEARCH_MAX_ANGLE = 180
SEARCH_SWEEP_SPEED = 8.0         # Target deg/s during search (visible slow motion)
SEARCH_SWEEP_STEP = 3            # Degrees per search tick (from actual servo position)
SEARCH_START_DIRECTION = "last"  # Unused when SEARCH_EXPAND_ENABLED is False
SEARCH_EXPAND_ENABLED = False    # Simple 0→180→0 only (no chaotic expand)
SEARCH_REACQUIRE_FRAMES = 2      # Frames the original target must be re-seen to re-lock
SEARCH_ENDPOINT_DWELL_SEC = 0.5   # Brief pause at 0° and 180° only
SEARCH_SWEEP_CATCHUP_DEG = 4     # Next step only when ESP within this many ° of last command
SEARCH_STUCK_TIMEOUT_SEC = 8.0   # Resend same target if ESP angle unchanged this long

# Legacy fixed sweep (used only if SEARCH_EXPAND_ENABLED is False)
FRAMES_BEFORE_SEARCH = 24
SEARCH_INTERVAL_SEC = 0.15
SEARCH_SWEEP_POSITIONS = [
    0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180,
    165, 150, 135, 120, 105, 90, 75, 60, 45, 30, 15, 0,
]

# ----------------------------------------------------------------------------
# BOUNDING-BOX COLORS (BGR) — Issue #2
# ----------------------------------------------------------------------------
COLOR_UNKNOWN = (0, 0, 255)     # Red
COLOR_KNOWN = (255, 0, 0)       # Blue (recognized, not locked)
COLOR_LOCKED = (0, 255, 0)      # Green (locked target)
COLOR_LOST = (0, 165, 255)      # Orange (lock lost / searching)
COLOR_HUD = (0, 255, 0)         # Debug overlay text

# ============================================================================
# DEBUG & LOGGING
# ============================================================================

DEBUG_MODE = False
VERBOSE_LOGGING = False
TRACKING_LOG_ENABLED = True  # Console logs for lock visibility and servo decisions
TRACKING_STATUS_INTERVAL_SEC = 2.0  # Min seconds between repeated hold/missing messages
SAVE_DEBUG_FRAMES = False

# ============================================================================
# WEB DASHBOARD
# ============================================================================

DASHBOARD_ENABLED = False
DASHBOARD_HOST = "127.0.0.1"  # Use 0.0.0.0 to view from other devices on LAN
DASHBOARD_PORT = 8765
DASHBOARD_STREAM_FPS = 12  # MJPEG stream rate (lower = less CPU)
DASHBOARD_SERVO_HISTORY = 40
DASHBOARD_HEADLESS = False  # True = no OpenCV window, browser only

# ============================================================================
# QUALITY CHECKS
# ============================================================================

REQUIRE_ALIGNED_CROP_SIZE = (112, 112)
MIN_FACE_BBOX_AREA = 60 * 60  # Minimum 60x60 for detection

# Geometry constraints
KPS_MUST_BE_IN_HAAR_BOX = True
KPS_IN_BOX_MARGIN = 0.35  # Generous margin
KPS_IN_BOX_MIN_RATIO = 0.60  # At least 60% of points inside box


def ensure_dirs() -> None:
    """Create all necessary directories if they don't exist."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    ENROLL_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_ALIGNED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_dirs()
    print("Configuration loaded and directories created.")
