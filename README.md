# Taichung Traffic Light Detection Web App

## 專案介紹
使用台中市政府公開 CCTV，
搭配 Roboflow 模型進行即時紅綠燈辨識。

## 功能
- 顯示台中市 CCTV 清單
- 搜尋路口
- 點擊切換 CCTV
- 即時影像串流
- 紅 / 黃 / 綠燈 AI 偵測
- 顯示 confidence
- CCTV 自動重連
- 政府 API 失敗自動 retry

## 使用技術
- Python
- OpenCV
- FastAPI
- Jinja2
- HTML / CSS / JavaScript
- Roboflow Hosted Inference API
- ThreadPoolExecutor

## 系統流程
政府 CCTV API
→ CCTV 串流
→ OpenCV
→ Roboflow AI
→ FastAPI
→ Browser

## 啟動方式
雙擊：

start_traffic_light.cmd

或：

uvicorn app:app --reload

## 安全
API Key 使用 .env 保存，
.env 已加入 .gitignore。