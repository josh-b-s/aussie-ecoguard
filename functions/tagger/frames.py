import cv2


def extract_frames(video_path, interval_seconds=10):
    """Yield one JPEG (bytes) every interval_seconds, starting at 0s."""
    capture = cv2.VideoCapture(video_path)
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps <= 0 or frame_count <= 0:
            raise ValueError(f"cannot read video metadata: {video_path}")

        duration = frame_count / fps
        second = 0
        while second < duration:
            capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            ok, frame = capture.read()
            if not ok:
                if second == 0:
                    raise ValueError(f"cannot decode video: {video_path}")
                # The frame count estimate can overshoot the last readable frame
                break
            yield cv2.imencode(".jpg", frame)[1].tobytes()
            second += interval_seconds
    finally:
        capture.release()
