import os
import cv2
import time
import requests
import json

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from inference_sdk import InferenceHTTPClient
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

API_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=6c9f5fd5-d74c-4450-9339-1a00e6cda2e6"

app = FastAPI()

MODEL_ID = "a12754213-gmail-com/my-first-project-fkmn7-5-rfdetr-small-t1"

# 讀取 .env
load_dotenv()

# 取得 Roboflow API Key
api_key = os.getenv("ROBOFLOW_API_KEY")

if api_key is None:
    raise RuntimeError("找不到 Roboflow API Key")

# 連線 Roboflow Hosted API
client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=api_key
)

# HTML 頁面
templates = Jinja2Templates(directory="templates")

# CSS 等靜態檔案
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# 取得政府 CCTV 清單
# 取得政府 CCTV 清單
def get_cameras():

    # 最多嘗試 5 次
    for attempt in range(5):

        try:
            response = requests.get(
                API_URL,
                timeout=30
            )

            print(
                f"政府 API 第 {attempt + 1} 次：",
                response.status_code
            )

            # 成功取得資料
            if (
                response.status_code == 200
                and len(response.content) > 0
            ):
                text = response.content.decode("utf-8-sig")

                try:
                    cameras = json.loads(text)

                    print("政府 API 資料取得成功")

                    return cameras

                except json.JSONDecodeError:
                    print("政府 API JSON 解析失敗")

            else:
                print("政府 API 暫時無法使用")

        except requests.RequestException as e:
            print("政府 API 連線錯誤:", e)

        # 失敗後等 3 秒
        time.sleep(3)

    # 5 次全部失敗
    raise RuntimeError("政府 API 多次連線失敗")
# 首頁
@app.get("/")
def home(request: Request):

    cameras = get_cameras()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "cameras": cameras
        }
    )

# 單一 CCTV 頁面
@app.get("/camera/{camera_index}")
def camera_page(
    request: Request,
    camera_index: int
):

    cameras = get_cameras()
    camera = cameras[camera_index]

    return templates.TemplateResponse(
        request=request,
        name="camera.html",
        context={
            "camera": camera,
            "camera_index": camera_index
        }
    )

#「畫框」
def draw_predictions(frame, result):

    if result is None:
        return frame

    frame_h, frame_w = frame.shape[:2]

    for pred in result.get("predictions", []):

        x = pred["x"]
        y = pred["y"]
        w = pred["width"]
        h = pred["height"]

        confidence = pred["confidence"]
        class_name = pred["class"]

        # 信心度太低就略過
        if confidence < 0.4:
            continue

        # 中心點座標 -> 左上角 / 右下角
        x1 = int(x - w / 2)
        y1 = int(y - h / 2)
        x2 = int(x + w / 2)
        y2 = int(y + h / 2)

        # 避免座標超出畫面
        x1 = max(0, min(x1, frame_w - 1))
        y1 = max(0, min(y1, frame_h - 1))
        x2 = max(0, min(x2, frame_w - 1))
        y2 = max(0, min(y2, frame_h - 1))

        # 不同燈號不同顏色（BGR）
        if class_name == "red_light":
            color = (0, 0, 255)
        elif class_name == "yellow_light":
            color = (0, 255, 255)
        elif class_name == "green_light":
            color = (0, 255, 0)
        else:
            color = (255, 255, 255)

        # 畫框
        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            color,
            1
        )

        # 顯示標籤
        label = f"{class_name} {confidence:.2f}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.45
        thickness = 1
        padding = 3

        # 計算文字大小
        (text_w, text_h), baseline = cv2.getTextSize(
            label,
            font,
            font_scale,
            thickness
        )

        label_h = text_h + baseline + padding * 2

        # 上面有空間就放框上面，否則放框下面
        if y1 >= label_h:
            bg_y1 = y1 - label_h
            bg_y2 = y1
        else:
            bg_y1 = y2
            bg_y2 = min(y2 + label_h, frame_h - 1)

            # 如果框下面也不夠，就貼在畫面底部
            if bg_y2 - bg_y1 < label_h:
                bg_y2 = frame_h - 1
                bg_y1 = max(0, bg_y2 - label_h)

        # 避免標籤超出畫面右側
        bg_x1 = min(x1, max(0, frame_w - text_w - padding * 2))
        bg_x2 = min(bg_x1 + text_w + padding * 2, frame_w - 1)

        # 畫標籤底色
        cv2.rectangle(
            frame,
            (bg_x1, bg_y1),
            (bg_x2, bg_y2),
            color,
            -1
        )

        # 寫上文字
        text_x = bg_x1 + padding
        text_y = bg_y1 + padding + text_h

        cv2.putText(
            frame,
            label,
            (text_x, text_y),
            font,
            font_scale,
            (0, 0, 0),
            thickness
        )

    return frame

# 取得真正的 CCTV 串流網址
def get_stream_url(camera):

    cctv_response = requests.get(
        camera["url"],
        timeout=30
    )

    soup = BeautifulSoup(
        cctv_response.text,
        "html.parser"
    )

    img = soup.find("img")

    if img is None:
        return None

    return img.get("src")


# 持續產生 CCTV 畫面
def generate_video(camera_index):

    cameras = get_cameras()
    camera = cameras[camera_index]

    stream_url = get_stream_url(camera)

    if stream_url is None:
        print("找不到 CCTV 串流網址")
        return

    # 記錄上一次 API 推論時間
    last_inference_time = 0

    # 保存最新一次推論結果
    latest_result = None

    # 建立背景執行緒，避免 API 卡住畫面
    executor = ThreadPoolExecutor(max_workers=1)

    # 保存正在執行的 API 任務
    inference_future = None

    try:
        while True:

            # 開啟 CCTV 串流
            cap = cv2.VideoCapture(stream_url)

            if not cap.isOpened():
                print("CCTV 串流開啟失敗")
                time.sleep(2)
                continue

            print("網站 CCTV 串流連線成功")

            while True:

                ret, frame = cap.read()

                # CCTV 中斷就重新連線
                if not ret:
                    print("網站 CCTV 串流中斷，重新連線")
                    break

                # 如果背景 API 已經完成，拿到結果
                if inference_future is not None and inference_future.done():
                    try:
                        latest_result = inference_future.result()
                        print(latest_result)
                    except Exception as e:
                        print("Roboflow API 錯誤:", e)

                    inference_future = None

                # 每 1 秒送一張 frame 去 Roboflow
                if (
                    inference_future is None
                    and time.time() - last_inference_time >= 1
                ):
                    frame_for_api = frame.copy()

                    inference_future = executor.submit(
                        client.infer,
                        frame_for_api,
                        model_id=MODEL_ID
                    )

                    last_inference_time = time.time()

                # 把最新偵測結果畫到畫面上
                frame = draw_predictions(frame, latest_result)

                # 轉成 JPG
                success, buffer = cv2.imencode(".jpg", frame)

                if not success:
                    continue

                frame_bytes = buffer.tobytes()

                # 傳給瀏覽器
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame_bytes
                    + b"\r\n"
                )

            cap.release()
            time.sleep(1)

    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# CCTV 網頁影像串流
@app.get("/video_feed/{camera_index}")
def video_feed(camera_index: int):

    return StreamingResponse(
        generate_video(camera_index),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )