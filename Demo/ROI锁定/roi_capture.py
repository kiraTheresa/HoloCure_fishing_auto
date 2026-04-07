import cv2
import mss
import numpy as np
import win32gui
import time

from config import ROI


def find_window(title):
    hwnd = win32gui.FindWindow(None, title)
    if hwnd == 0:
        return None
    return hwnd


def get_client_rect(hwnd):
    client_rect = win32gui.GetClientRect(hwnd)
    client_width = client_rect[2]
    client_height = client_rect[3]

    client_left_top = win32gui.ClientToScreen(hwnd, (0, 0))
    client_left = client_left_top[0]
    client_top = client_left_top[1]

    return client_left, client_top, client_width, client_height


def main():
    target_title = "HoloCure"

    x1, y1, x2, y2 = ROI["x1"], ROI["y1"], ROI["x2"], ROI["y2"]
    print(f"ROI区域: ({x1},{y1}) -> ({x2},{y2}), 尺寸: {x2-x1}x{y2-y1}")

    hwnd = find_window(target_title)
    if hwnd is None:
        print(f"窗口 '{target_title}' 未找到，请确认窗口已打开")
        return

    print(f"已找到窗口: {target_title} (hwnd={hwnd})")

    with mss.mss() as sct:
        prev_time = time.time()
        fps = 0

        while True:
            left, top, width, height = get_client_rect(hwnd)

            monitor = {
                "left": left,
                "top": top,
                "width": width,
                "height": height
            }

            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            roi_frame = frame[y1:y2, x1:x2]

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, f"ROI:({x1},{y1})-({x2},{y2})", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

            curr_time = time.time()
            fps = 1 / (curr_time - prev_time)
            prev_time = curr_time

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Original + ROI", frame)
            cv2.imshow("ROI Cropped", roi_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
