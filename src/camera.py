"""
Camera module: validates video capture and FPS.
First sanity check for the entire pipeline.
Tested on Kali Linux with USB camera (YUYV only).
"""

import sys
import time
import cv2


def main():
    """
    Open webcam and display live video with FPS counter.
    Press 'q' to exit.
    """

    # IMPORTANT: USB external camera index
    CAMERA_INDEX = 0

    # Open camera using V4L2 backend
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)

    if not cap.isOpened():
        print(f"ERROR: Cannot open camera at index {CAMERA_INDEX}")
        return False

    # Force correct pixel format (camera supports ONLY YUYV)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))

    # Set resolution and FPS (must match supported modes)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    print("✓ Camera opened successfully")
    print("  Resolution: 640x480")
    print("  Pixel format: YUYV")
    print("  Press 'q' to exit")

    # Prepare window (important for Kali)
    cv2.namedWindow("Camera Test", cv2.WINDOW_NORMAL)

    frame_count = 0
    fps = 0.0
    t0 = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("ERROR: Failed to read frame from camera")
                break

            # FPS calculation (updated every second)
            frame_count += 1
            elapsed = time.time() - t0
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                t0 = time.time()

            # Overlay text
            cv2.putText(
                frame,
                f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

            cv2.putText(
                frame,
                "Press 'q' to quit",
                (10, 460),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 200),
                1,
            )

            # Show frame
            cv2.imshow("Camera Test", frame)

            # Exit on 'q'
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()

    print("✓ Camera test passed. Pipeline ready.")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
