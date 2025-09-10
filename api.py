from __future__ import annotations

from enum import Enum
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
import uvicorn
import os
import time
import argparse
import tempfile
import subprocess
import shutil
import mimetypes
import logging
import json
import io
from datetime import datetime
from urllib.parse import urlparse
import httpx
from typing import Dict, Any

from indextts.infer import IndexTTS


# ========= 启动参数 =========
parser = argparse.ArgumentParser(description="IndexTTS API")
parser.add_argument("--port", type=int, default=6008, help="API service port")
parser.add_argument("--host", type=str, default="0.0.0.0", help="API bind host")
parser.add_argument("--model_dir", type=str, default="checkpoints", help="Model directory")
parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")
parser.add_argument("--log_file", type=str, default="logs/indextts_api.log", help="Log file path")
api_args = parser.parse_args()


# ========= 日志配置 =========
def setup_logging():
    """设置日志配置"""
    # 创建日志目录
    log_dir = os.path.dirname(api_args.log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 配置根日志器
    logging.basicConfig(
        level=getattr(logging, api_args.log_level),
        format=log_format,
        datefmt=date_format,
        handlers=[
            # 文件处理器
            logging.FileHandler(api_args.log_file, encoding='utf-8'),
            # 控制台处理器
            logging.StreamHandler()
        ]
    )
    
    # 创建API专用日志器
    api_logger = logging.getLogger("IndexTTS-API")
    return api_logger

# 初始化日志
logger = setup_logging()
logger.info(f"IndexTTS API 启动中... 日志级别: {api_args.log_level}, 日志文件: {api_args.log_file}, 运行模式: 无存储模式")


# ========= 模型初始化与文件检查 =========
logger.info("开始检查模型文件...")
required_files = ["bigvgan_generator.pth", "bpe.model", "gpt.pth", "config.yaml"]
for file in required_files:
    path = os.path.join(api_args.model_dir, file)
    if not os.path.exists(path):
        logger.error(f"缺少必需的模型文件: {file} ({path})")
        raise FileNotFoundError(f"Missing required model file: {file} ({path})")
    else:
        logger.info(f"模型文件检查通过: {file}")

logger.info("开始初始化IndexTTS模型...")
start_time = time.time()
tts = IndexTTS(
    model_dir=api_args.model_dir,
    cfg_path=os.path.join(api_args.model_dir, "config.yaml"),
)
init_time = time.time() - start_time
logger.info(f"IndexTTS模型初始化完成，耗时: {init_time:.2f}秒")


# ========= FastAPI =========
app = FastAPI(title="IndexTTS API (JSON only)")

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有HTTP请求"""
    start_time = time.time()
    
    # 获取客户端IP
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # 记录请求开始
    logger.info(f"请求开始 - {request.method} {request.url.path} - 客户端IP: {client_ip} - User-Agent: {user_agent}")
    
    # 处理请求
    response = await call_next(request)
    
    # 计算处理时间
    process_time = time.time() - start_time
    
    # 记录请求完成
    logger.info(f"请求完成 - {request.method} {request.url.path} - 状态码: {response.status_code} - 处理时间: {process_time:.3f}秒")
    
    return response

# CORS（按需收紧 allow_origins）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========= 请求体 / 枚举 =========
class InferMode(str, Enum):
    standard = "standard"  # 原“普通推理”
    batch = "batch"        # 原“批次推理”


class TTSBody(BaseModel):
    prompt_url: HttpUrl = Field(..., description="Reference audio URL (http/https)")
    text: str = Field(..., description="Target text to synthesize")
    infer_mode: InferMode = Field(
        InferMode.standard,
        description="Inference mode: 'standard' or 'batch'",
    )
    max_text_tokens_per_sentence: int = 120
    sentences_bucket_max_size: int = 4
    do_sample: bool = True
    top_p: float = 0.8
    top_k: int = 30
    temperature: float = 1.0
    length_penalty: float = 0.0
    num_beams: int = 3
    repetition_penalty: float = 10.0
    max_mel_tokens: int = 600


# ========= 工具函数 =========
def _ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None


def _guess_ext_from_headers(url: str, content_type: str | None) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext
    path = urlparse(str(url)).path
    ext = os.path.splitext(path)[1]
    return ext if ext else ".bin"


def _to_wav_with_ffmpeg(inp_path: str, out_path: str) -> None:
    # 按需调整采样率/声道
    cmd = ["ffmpeg", "-y", "-i", inp_path, "-ar", "16000", "-ac", "1", out_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


async def _fetch_to_local_wav(url: str) -> str:
    # 仅允许 http/https
    scheme = urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are supported")

    # 超时配置：连接 30s，读取 120s（其余默认 60s）
    timeout = httpx.Timeout(60.0, connect=30.0, read=120.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers={"User-Agent": "IndexTTS/0.1"})
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Fetch failed: {e}") from e

        if resp.status_code != 200:
            # 如需更详细排障可附带 resp.text（注意可能很大）
            raise HTTPException(status_code=502, detail=f"Fetch audio failed: {resp.status_code}")

        content = resp.content
        if not content or len(content) < 16:
            raise HTTPException(status_code=422, detail="Audio content is empty or too short")

        # 保存原始文件（保留扩展名便于排查）
        ext = _guess_ext_from_headers(url, resp.headers.get("content-type"))
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
            raw_path = f.name
            f.write(content)

    if not _ffmpeg_exists():
        raise HTTPException(status_code=500, detail="ffmpeg not installed, cannot convert to WAV")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f2:
        wav_path = f2.name
    try:
        _to_wav_with_ffmpeg(raw_path, wav_path)
    finally:
        try:
            os.remove(raw_path)
        except Exception:
            pass
    return wav_path


# ========= 健康检查端点 =========
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "IndexTTS API",
        "version": "1.0.0"
    }

# ========= 接口：仅 JSON Body =========
@app.post("/tts")
async def tts_json(body: TTSBody):
    """
    JSON body example:
    {
      "prompt_url": "https://example.com/sample.mp3",
      "text": "hello world",
      "infer_mode": "standard",        // or "batch"
      "max_text_tokens_per_sentence": 120,
      "sentences_bucket_max_size": 4,
      "do_sample": true,
      "top_p": 0.8,
      "top_k": 30,
      "temperature": 1.0,
      "length_penalty": 0.0,
      "num_beams": 3,
      "repetition_penalty": 10.0,
      "max_mel_tokens": 600
    }
    Returns: audio/wav stream (binary) - 直接返回音频数据流，不保存文件
    """
    request_id = f"req_{int(time.time() * 1000)}"
    logger.info(f"[{request_id}] TTS请求开始 - 文本长度: {len(body.text)} 字符, 推理模式: {body.infer_mode}")
    logger.debug(f"[{request_id}] 请求参数: {body.dict()}")
    
    try:

        # 下载并转 WAV
        logger.info(f"[{request_id}] 开始下载参考音频: {body.prompt_url}")
        download_start = time.time()
        prompt_wav = await _fetch_to_local_wav(str(body.prompt_url))
        download_time = time.time() - download_start
        logger.info(f"[{request_id}] 参考音频下载完成，耗时: {download_time:.2f}秒")
        
        # 推理参数
        kwargs = {
            "do_sample": bool(body.do_sample),
            "top_p": float(body.top_p),
            "top_k": int(body.top_k) if int(body.top_k) > 0 else None,
            "temperature": float(body.temperature),
            "length_penalty": float(body.length_penalty),
            "num_beams": int(body.num_beams),
            "repetition_penalty": float(body.repetition_penalty),
            "max_mel_tokens": int(body.max_mel_tokens),
        }

        # TTS推理：直接返回音频流，不存储文件
        logger.info(f"[{request_id}] 开始TTS推理 - 模式: {body.infer_mode}")
        inference_start = time.time()
        
        if body.infer_mode == InferMode.standard:
            audio_data = tts.infer(
                prompt_wav,
                body.text,
                output_path=None,  # 不保存文件
                max_text_tokens_per_sentence=int(body.max_text_tokens_per_sentence),
                **kwargs,
            )
        else:  # InferMode.batch
            audio_data = tts.infer_fast(
                prompt_wav,
                body.text,
                output_path=None,  # 不保存文件
                max_text_tokens_per_sentence=int(body.max_text_tokens_per_sentence),
                sentences_bucket_max_size=int(body.sentences_bucket_max_size),
                **kwargs,
            )
        
        inference_time = time.time() - inference_start
        logger.info(f"[{request_id}] TTS推理完成，耗时: {inference_time:.2f}秒")

        # 清理临时 prompt
        try:
            os.remove(prompt_wav)
            logger.debug(f"[{request_id}] 临时文件清理完成")
        except Exception as e:
            logger.warning(f"[{request_id}] 临时文件清理失败: {e}")

        # 处理音频数据并返回流
        if audio_data and len(audio_data) == 2:
            sampling_rate, wav_data = audio_data
            import numpy as np
            import wave
            
            # 确保音频数据是正确的格式
            if isinstance(wav_data, np.ndarray):
                # 如果是numpy数组，转换为int16格式
                if wav_data.dtype != np.int16:
                    wav_data = wav_data.astype(np.int16)
                
                # 创建WAV文件格式的字节流
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # 单声道
                    wav_file.setsampwidth(2)  # 16位 = 2字节
                    wav_file.setframerate(sampling_rate)
                    wav_file.writeframes(wav_data.tobytes())
                
                wav_bytes = wav_buffer.getvalue()
                
                logger.info(f"[{request_id}] TTS请求成功完成 - 音频数据大小: {len(wav_bytes)} bytes, 采样率: {sampling_rate}Hz")
                
                return StreamingResponse(
                    io.BytesIO(wav_bytes),
                    media_type="audio/wav",
                    headers={
                        "Content-Disposition": f"attachment; filename=tts_output_{request_id}.wav",
                        "X-Sampling-Rate": str(sampling_rate),
                        "X-Request-ID": request_id
                    }
                )
            else:
                logger.error(f"[{request_id}] 音频数据不是numpy数组: {type(wav_data)}")
                raise HTTPException(status_code=500, detail="Invalid audio data format")
        else:
            logger.error(f"[{request_id}] 音频数据格式错误: {type(audio_data)}")
            raise HTTPException(status_code=500, detail="Audio generation failed")

    except HTTPException as e:
        logger.error(f"[{request_id}] HTTP异常: {e.detail}")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"[{request_id}] 音频转码失败: {e}")
        raise HTTPException(status_code=500, detail="Audio transcoding failed (ffmpeg not available or errored)")
    except Exception as e:
        logger.error(f"[{request_id}] 未知异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========= 启动 =========
if __name__ == "__main__":
    logger.info(f"IndexTTS API 服务启动 - 地址: {api_args.host}:{api_args.port}")
    logger.info(f"API文档地址: http://{api_args.host}:{api_args.port}/docs")
    logger.info(f"健康检查地址: http://{api_args.host}:{api_args.port}/health")
    
    try:
        uvicorn.run(app, host=api_args.host, port=api_args.port, log_level=api_args.log_level.lower())
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务启动失败: {e}", exc_info=True)
    finally:
        logger.info("IndexTTS API 服务已关闭")
