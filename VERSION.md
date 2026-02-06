# 版本说明

## 当前版本
- **稳定版**: 3.0.7
- **测试版**: test-20260206-1

## Docker 镜像

### 稳定版
```bash
docker pull 85423296/t3mt:latest
# 或指定版本
docker pull 85423296/t3mt:3.0.7
```

### 测试版 (用于测试新功能)
```bash
docker pull 85423296/t3mt:test
```

## 快速部署

### 稳定版
```bash
# 下载配置
wget https://raw.githubusercontent.com/qq85423296/t3mt/main/docker-compose.yml

# 启动服务
docker-compose up -d

# 访问: http://localhost:8520
```

### 测试版
```bash
# 下载配置
wget https://raw.githubusercontent.com/qq85423296/t3mt/test/docker-compose.test.yml

# 启动服务
docker-compose -f docker-compose.test.yml up -d

# 访问: http://localhost:8521
```

## 版本区别

| 特性 | 稳定版 (latest) | 测试版 (test) |
|------|----------------|---------------|
| 稳定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 新功能 | 较少 | 较多 |
| 更新频率 | 每月 1-2 次 | 每周 1-2 次 |
| 推荐场景 | 生产环境 | 测试环境 |
| Bug 风险 | 低 | 中等 |

## 更新方式

### 稳定版
```bash
docker-compose down
docker pull 85423296/t3mt:latest
docker-compose up -d
```

### 测试版
```bash
docker-compose -f docker-compose.test.yml down
docker pull 85423296/t3mt:test
docker-compose -f docker-compose.test.yml up -d
```

## 详细文档
- [Docker 镜像发布流程](docs/Docker镜像发布流程.md)
- [Git 提交和 Docker 自动构建说明](docs/Git提交和Docker自动构建说明.md)
