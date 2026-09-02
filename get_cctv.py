import cv2          # 用來讀取、顯示 CCTV 畫面
import os
import requests     # 用來向網站/API取得資料
import json         # 用來處理 JSON 資料
import time

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from inference_sdk import InferenceHTTPClient
from concurrent.futures import ThreadPoolExecutor

API_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=6c9f5fd5-d74c-4450-9339-1a00e6cda2e6"

# 向台中市政府 API 下載資料
# 最多嘗試取得政府 API 5 次
data = None

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
        if response.status_code == 200 and len(response.content) > 0:
            text = response.content.decode("utf-8-sig")
            try:
                data = json.loads(text)
                print("政府 API 資料取得成功")
                break

            except json.JSONDecodeError:
                print("政府 API 回傳的不是正常 JSON")
        else:
            print("政府 API 暫時無法使用")
    except requests.RequestException as e:
        print("政府 API 連線錯誤:", e)
    # 失敗後等 3 秒再試
    time.sleep(3)
# 5 次都失敗才停止
if data is None:
    print("政府 API 多次連線失敗，程式停止")
    exit()
# 讀取 .env
load_dotenv()

# 取得 Roboflow API Key
api_key = os.getenv("ROBOFLOW_API_KEY")

if api_key is None:
    print("找不到 Roboflow API Key")
    exit()

# 連線 Roboflow Hosted API
client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=api_key
)


# # 顯示 API 是否請求成功，例如 200 代表成功
# print("HTTP 狀態碼:", response.status_code)
# # 顯示下載回來的資料格式
# print("資料類型:", response.headers.get("Content-Type"))
# # 顯示下載回來的資料大小
# print("下載大小:", len(response.content),"bytes")


# # 顯示前 5 支 CCTV 的重要資訊
# for cctv in data[:5]:
#     print("路口:", cctv["roadsection"])
#     print("網址:", cctv["url"])
#     print("狀態:", cctv["status"])
#     print("="*20)

# 顯示前 20 支 CCTV
for i, cctv in enumerate(data[:20]):
    print(i, cctv["roadsection"])
# 選擇 CCTV
camera_index = int(input("\n請輸入 CCTV編號: "))
# 取得選擇的 CCTV 網址
cctv_url = data[camera_index]["url"]
print("目前 CCTV:", data[camera_index]["roadsection"])

cctv_response = requests.get(
    cctv_url,
    timeout=30
)

# # 看 CCTV 網址是否能正常連線
# print("CCTV HTTP 狀態碼:", cctv_response.status_code)
# # 看 CCTV 回傳的資料格式
# print(
#     "CCTV Content-Type:",
#     cctv_response.headers.get("Content-type")
# )
# # 看實際下載了多少資料
# print(
#     "CCTV 資料大小:", 
#     len(cctv_response.content),
#     "bytes"
# )
# # 如果是網頁，先印前 500 個字看看
# print(
#     cctv_response.text[:500]
# )

# 解析 CCTV 網頁 HTML
soup = BeautifulSoup(
    cctv_response.text,
    "html.parser"
)
# 找到網頁裡的第一個 img
img = soup.find("img")
# 確認有找到影像網址
if img is None:
    print("找不到 CCTV 影像")
    exit()


# 記錄上一次 API 推論時間
last_inference_time = 0
# 保存最新一次推論結果
latest_result = None
# 建立背景執行緒，避免 API 卡住 CCTV 畫面
executor = ThreadPoolExecutor(max_workers=1)
# 保存正在執行的 API 任務
inference_future = None
# 取得真正的影像串流網址
stream_url = img.get("src")
# 控制程式是否繼續執行
running = True

while running:
    # 開啟 CCTV 串流
    cap = cv2.VideoCapture(stream_url)

    if not cap.isOpened():
        print("CCTV 串流開啟失敗")
        time.sleep(2)
        continue
    start_time = time.time()
    print("CCTV 串流連線成功")
    while True:
        ret, frame = cap.read()
    #串流中斷
        if not ret:
            print("CCTV 串流中斷，2 秒後重新連線...")
            elapsed = time.time() - start_time
            print(
                "CCTV 串流中斷，維持時間:",
                round(elapsed, 1),
                "秒"
            )
            break 
        if inference_future is not None and inference_future.done():
            try:
                latest_result = inference_future.result()
                print(latest_result)
            except Exception as e:
                print("Roboflow API 錯誤:", e)
            inference_future = None
        # 每 1 秒送一張畫面，而且上一個 API 必須已經完成
        if(
            inference_future is None 
            and time.time() - last_inference_time >=1
        ):
            frame_for_api = frame.copy()
            inference_future = executor.submit(
                client.infer,
                frame_for_api,
                model_id="a12754213-gmail-com/my-first-project-fkmn7-5-rfdetr-small-t1"
            )
            last_inference_time = time.time()
        
        if latest_result is not None:
            for pred in latest_result["predictions"]:
                x = pred["x"]
                y = pred["y"]
                w = pred["width"]
                h = pred["height"]
                confidence = pred["confidence"]
                class_name = pred["class"]
        # Roboflow 回傳的是中心點座標，要轉成左上角/右下角
                x1 = int(x - w / 2)
                y1 = int(y - h / 2)
                x2 = int(x + w / 2)
                y2 = int(y + h / 2)
        # 畫框
                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )
                # 顯示類別與信心度
                label = f"{class_name} {confidence:.2f}"

                cv2.putText(
                    frame,
                    label,
                    (x1, y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )
        cv2.imshow("Taichung CCTV",frame)
        # 按 ESC 結束程式
        if cv2.waitKey(30) & 0xFF == 27:
            running = False
            break    
        # 按 X 結束程式
        if cv2.getWindowProperty(
            "Taichung CCTV",
            cv2.WND_PROP_VISIBLE
        ) < 1:
            running = False
            break

    cap.release()
    # 如果不是使用者關閉，就重新連線 
    if running:
        time.sleep(2)

executor.shutdown(wait=False, cancel_futures=True)
cv2.destroyAllWindows()

