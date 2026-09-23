# Basketball Analysis Docker Image
# Python 3.13 + YOLOv8 + OpenCV + NBA API

FROM python:3.13-slim

# メタデータ
LABEL maintainer="Basketball Flow Lab"
LABEL description="バスケットボール動画分析環境（シュートチャート・Play-by-Play自動生成）"

# 環境変数
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Tokyo

# システムパッケージインストール
RUN apt-get update && apt-get install -y \
    # ビルドツール
    build-essential \
    cmake \
    pkg-config \
    # OpenCV依存
    libopencv-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    # 動画処理
    ffmpeg \
    # その他
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Python依存パッケージインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコード
COPY src/ ./src/
COPY docs/ ./docs/
COPY *.py ./
COPY *.sh ./

# データ・出力ディレクトリ作成
RUN mkdir -p data/videos data/cache outputs/three_games outputs/images

# 実行権限付与
RUN chmod +x *.sh

# デフォルトコマンド
CMD ["python", "analyze_three_games_fast.py"]
