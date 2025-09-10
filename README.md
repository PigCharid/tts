# IndexTTS API

這是IndexTTS的獨立API版本，提供REST API介面來使用IndexTTS文本轉語音功能。

## 特色

- ✅ **輕量化**：專案大小僅7.5MB（不含模型）
- ✅ **自動下載**：模型檔案會在安裝時自動下載
- ✅ **繁體中文**：完整的繁體中文介面
- ✅ **獨立運行**：不依賴原始IndexTTS專案
- ✅ **Docker支援**：提供完整的容器化部署方案
- ✅ **無存儲模式**：直接返回音頻流，不保存文件，適合微服務架構

## 快速開始

### 方法一：直接安裝

```bash
# 1. 創建虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 2. 自動安裝（包含模型下載）
python setup_api.py

# 3. 啟動API服務
python api.py
```

### 方法二：手動安裝

```bash
# 1. 創建虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 2. 安裝ffmpeg
pip install ffmpeg

# 3. 安裝PyTorch (CUDA版本)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# 4. 安裝其他依賴
pip install -r requirements.txt

# 5. 安裝IndexTTS包
pip install -e .

# 6. 下載模型檔案
huggingface-cli download IndexTeam/IndexTTS-1.5 \
  config.yaml bigvgan_discriminator.pth bigvgan_generator.pth bpe.model dvae.pth gpt.pth unigram_12000.vocab \
  --local-dir checkpoints

# 7. 啟動API服務
python api.py
```

### 方法三：Docker部署

```bash
# 啟動服務（開發模式，支援即時更新）
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 停止服務
docker-compose down
```

## API使用

API啟動後，訪問 `http://localhost:6008/docs` 查看完整的API文檔。

### 基本使用範例

#### curl
```bash
curl -X POST "http://localhost:6008/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_url": "https://example.com/reference.wav",
    "text": "你好，這是測試文本",
    "infer_mode": "standard"
  }' \
  --output result.wav
```

#### Python
```python
import requests

response = requests.post(
    "http://localhost:6008/tts",
    json={
        "prompt_url": "https://example.com/reference.wav",
        "text": "你好，這是測試文本",
        "infer_mode": "standard"
    }
)

# 直接保存音頻流
with open("output.wav", "wb") as f:
    f.write(response.content)

# 獲取音頻信息
sampling_rate = response.headers.get('X-Sampling-Rate')
request_id = response.headers.get('X-Request-ID')
print(f"採樣率: {sampling_rate}Hz, 請求ID: {request_id}")
```

## API端點

- **POST /tts** - 文本轉語音（返回音頻流）
- **GET /health** - 健康檢查
- **GET /docs** - API文檔（Swagger UI）
- **GET /redoc** - API文檔（ReDoc格式）

## 配置選項

```bash
python api.py --help
```

可用參數：
- `--port`: API服務端口（預設：6008）
- `--host`: API服務地址（預設：0.0.0.0）
- `--model_dir`: 模型目錄（預設：checkpoints）
- `--log_level`: 日誌級別（預設：INFO）
- `--log_file`: 日誌文件路徑（預設：logs/indextts_api.log）

## 系統需求

- Python 3.8+
- GPU記憶體 8GB+（推薦）
- 磁碟空間 4GB+（含模型檔案）
- 穩定的網路連接（首次下載模型）

## 注意事項

1. 首次安裝需要下載約3.5GB的模型檔案
2. 參考音頻建議使用清晰的wav格式檔案
3. 長文本建議使用"batch"模式以獲得更好的性能
4. API直接返回音頻流，不保存文件，適合微服務架構
5. 模型檔案會被自動忽略，不會提交到Git倉庫

