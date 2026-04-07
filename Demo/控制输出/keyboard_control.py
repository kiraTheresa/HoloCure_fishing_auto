import cv2
import mss
import numpy as np
import win32gui
import win32api
import win32con
import time
import os

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "project", "templates", "1920_1080", "opaque")
TEMPLATE_NAMES = ["up_54_63", "down_54_63", "left_60_57", "right_60_57", "circle_48_51"]
MATCH_THRESHOLD = 0.7
TOP_K = 5
TRIGGER_ZONE_WIDTH = 100

ROI = {
    "x1": 640,
    "y1": 720,
    "x2": 1220,
    "y2": 800
}

TEMPLATE_TO_KEY = {
    "up_54_63": "W",
    "down_54_63": "S",
    "left_60_57": "A",
    "right_60_57": "D",
    "circle_48_51": "SPACE"
}

KEY_CODE = {
    "W": 0x57,
    "A": 0x41,
    "S": 0x53,
    "D": 0x44,
    "SPACE": 0x20
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


def press_key(key_name):
    vk_code = KEY_CODE.get(key_name)
    if vk_code:
        win32api.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
        print(f"[按键] {key_name}")


def get_topk_from_result(result, template_name, k=5):
    flat = result.flatten()
    h, w = result.shape

    k = min(k, len(flat))
    indices = np.argpartition(flat, -k)[-k:]
    indices = indices[np.argsort(-flat[indices])]

    candidates = []
    for idx in indices:
        x = idx % w
        y = idx // w
        score = float(flat[idx])
        candidates.append({
            "name": template_name,
            "score": score,
            "loc": (x, y)
        })

    return candidates


def match_templates_topk(roi_gray, templates, k=5):
    all_candidates = []

    for name, tpl in templates.items():
        result = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
        candidates = get_topk_from_result(result, name, k)
        all_candidates.extend(candidates)

    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = all_candidates[:k]

    return top_candidates


def is_in_trigger_zone(loc, roi_width, trigger_width):
    x, y = loc
    trigger_x_start = roi_width - trigger_width
    return x >= trigger_x_start


def main():
    target_title = "HoloCure"

    x1, y1, x2, y2 = ROI["x1"], ROI["y1"], ROI["x2"], ROI["y2"]
    roi_width = x2 - x1
    roi_height = y2 - y1
    print(f"ROI区域: ({x1},{y1}) -> ({x2},{y2}), 尺寸: {roi_width}x{roi_height}")
    print(f"触发区域: 右侧 {TRIGGER_ZONE_WIDTH} 像素")

    templates = load_templates()
    if not templates:
        print("未加载到任何模板，退出")
        return

    hwnd = find_window(target_title)
    if hwnd is None:
        print(f"窗口 '{target_title}' 未找到，请确认窗口已打开")
        return

    print(f"已找到窗口: {target_title} (hwnd={hwnd})")
    print("控制输出已启动，按 q 退出")

    last_press_time = 0
    press_cooldown = 0.15

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

            top_candidates = match_templates_topk(roi_gray, templates, TOP_K)

            trigger_x = roi_width - TRIGGER_ZONE_WIDTH
            cv2.line(roi_frame, (trigger_x, 0), (trigger_x, roi_height), (255, 255, 0), 2)

            curr_time = time.time()
            triggered = False

            for i, cand in enumerate(top_candidates, 1):
                if cand["score"] >= MATCH_THRESHOLD:
                    name = cand["name"]
                    score = cand["score"]
                    loc = cand["loc"]

                    tpl_h, tpl_w = templates[name].shape[:2]
                    top_left = loc
                    bottom_right = (loc[0] + tpl_w, loc[1] + tpl_h)

                    in_trigger = is_in_trigger_zone(loc, roi_width, TRIGGER_ZONE_WIDTH)

                    if in_trigger:
                        color = (0, 255, 0)
                        key_name = TEMPLATE_TO_KEY.get(name)
                        if key_name and curr_time - last_press_time > press_cooldown:
                            press_key(key_name)
                            last_press_time = curr_time
                            triggered = True
                    else:
                        color = (128, 128, 128)

                    cv2.rectangle(roi_frame, top_left, bottom_right, color, 2)
                    cv2.putText(roi_frame, f"{name.split('_')[0]} ({score:.2f})",
                                (top_left[0], top_left[1] - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            fps = 1 / (curr_time - prev_time)
            prev_time = curr_time

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(roi_frame, f"Trigger Zone: Right {TRIGGER_ZONE_WIDTH}px",
                        (10, roi_height - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            cv2.imshow("Original + ROI", frame)
            cv2.imshow("ROI + Control", roi_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
