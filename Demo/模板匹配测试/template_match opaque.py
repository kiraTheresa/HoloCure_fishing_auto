import cv2
import mss
import numpy as np
import win32gui
import time
import os

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "project", "templates", "1920_1080","opaque")
TEMPLATE_NAMES = ["up_54_63", "down_54_63", "left_60_57", "right_60_57", "circle_48_51"]
MATCH_THRESHOLD = 0.7

ROI = {
    "x1": 640,
    "y1": 720,
    "x2": 1220,
    "y2": 800
}


def imread_unicode(path, flags=cv2.IMREAD_COLOR):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, flags)
    return img


def load_templates():
    templates = {}
    for name in TEMPLATE_NAMES:
        path = os.path.join(TEMPLATE_DIR, f"{name}.png")
        if os.path.exists(path):
            tpl = imread_unicode(path, cv2.IMREAD_GRAYSCALE)
            if tpl is not None:
                templates[name] = tpl
                print(f"已加载模板: {name} -> {tpl.shape[1]}x{tpl.shape[0]}")
            else:
                print(f"模板加载失败: {path}")
        else:
            print(f"模板文件不存在: {path}")
    return templates


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


def match_templates(roi_gray, templates):
    best_name = None
    best_val = -1
    best_loc = (0, 0)
    scores = {}

    for name, tpl in templates.items():
        result = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        scores[name] = round(max_val, 4)

        if max_val > best_val:
            best_val = max_val
            best_name = name
            best_loc = max_loc

    return best_name, best_val, best_loc, scores


def main():
    target_title = "HoloCure"

    x1, y1, x2, y2 = ROI["x1"], ROI["y1"], ROI["x2"], ROI["y2"]
    print(f"ROI区域: ({x1},{y1}) -> ({x2},{y2}), 尺寸: {x2-x1}x{y2-y1}")

    templates = load_templates()
    if not templates:
        print("未加载到任何模板，退出")
        return

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
            roi_gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)

            best_name, best_val, best_loc, scores = match_templates(roi_gray, templates)

            result_text = f"NONE"
            box_color = (128, 128, 128)

            if best_val >= MATCH_THRESHOLD:
                result_text = best_name.upper()
                box_color = (0, 255, 0)
                tpl_h, tpl_w = templates[best_name].shape[:2]
                top_left = best_loc
                bottom_right = (best_loc[0] + tpl_w, best_loc[1] + tpl_h)
                cv2.rectangle(roi_frame, top_left, bottom_right, box_color, 2)
                cv2.putText(roi_frame, f"{result_text} ({best_val:.3f})",
                            (top_left[0], top_left[1] - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
            else:
                cv2.putText(roi_frame, f"No Match (best={best_val:.3f})",
                            (10, roi_frame.shape[0] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            score_str = " | ".join([f"{k}:{v}" for k, v in scores.items()])
            print(f"[识别] {score_str} => 最佳:{best_name}({best_val:.4f})")

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

            curr_time = time.time()
            fps = 1 / (curr_time - prev_time)
            prev_time = curr_time

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Original + ROI", frame)
            cv2.imshow("ROI + Template Match", roi_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
