#!/bin/bash

# IndexTTS 多容器部署脚本

set -e

echo "=== IndexTTS 多容器部署脚本 ==="

# 检查Docker和Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 检查NVIDIA Docker支持
if ! docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi &> /dev/null; then
    echo "⚠️  NVIDIA Docker支持未检测到，GPU功能可能不可用"
    echo "请确保已安装nvidia-docker2"
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p checkpoints logs nginx/ssl

# 检查模型文件
echo "🔍 检查模型文件..."
if [ ! -f "checkpoints/gpt.pth" ]; then
    echo "⚠️  模型文件不存在，将在构建时自动下载"
    echo "首次构建可能需要较长时间（约3.5GB）"
fi

# 构建和启动服务
echo "🚀 构建和启动多容器服务..."
docker-compose -f docker-compose.multi.yaml up -d --build

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 检查服务状态
echo "📊 检查服务状态..."
docker-compose -f docker-compose.multi.yaml ps

# 健康检查
echo "🏥 执行健康检查..."
for i in {1..5}; do
    if curl -f http://localhost/health &> /dev/null; then
        echo "✅ 服务健康检查通过"
        break
    else
        echo "⏳ 等待服务启动... ($i/5)"
        sleep 10
    fi
done

# 显示访问信息
echo ""
echo "🎉 部署完成！"
echo ""
echo "📋 服务访问信息："
echo "  🌐 API服务: http://localhost"
echo "  📚 API文档: http://localhost/docs"
echo "  🏥 健康检查: http://localhost/health"
echo "  📊 Nginx状态: http://localhost/nginx_status"
echo "  📈 Prometheus: http://localhost:9090"
echo "  📊 Grafana: http://localhost:3000 (admin/admin123)"
echo ""
echo "🔧 管理命令："
echo "  查看日志: docker-compose -f docker-compose.multi.yaml logs -f"
echo "  停止服务: docker-compose -f docker-compose.multi.yaml down"
echo "  重启服务: docker-compose -f docker-compose.multi.yaml restart"
echo "  扩展实例: docker-compose -f docker-compose.multi.yaml up -d --scale indextts-api-1=2"
echo ""
echo "📝 注意事项："
echo "  - 确保有足够的GPU内存（每个实例至少8GB）"
echo "  - 监控日志文件大小，定期清理"
echo "  - 根据需要调整Nginx负载均衡配置"

