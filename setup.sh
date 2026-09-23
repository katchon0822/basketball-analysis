#!/bin/bash

################################################################################
# バスケットボール動画解析システム - セットアップスクリプト
#
# 使い方:
#   chmod +x setup.sh
#   ./setup.sh
################################################################################

set -e

# 色付きログ
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  🏀 バスケットボール動画解析システム セットアップ             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Python 3のチェック
if ! command -v python3 &> /dev/null; then
    echo "エラー: Python 3がインストールされていません"
    exit 1
fi

log_success "Python 3 検出: $(python3 --version)"

# 仮想環境作成
log_info "仮想環境を作成中..."
python3 -m venv venv
log_success "仮想環境作成完了"

# 仮想環境のアクティベート
log_info "仮想環境をアクティベート中..."
source venv/bin/activate

# 依存パッケージインストール
log_info "依存パッケージをインストール中..."
pip install --upgrade pip --quiet
pip install opencv-python matplotlib pandas numpy yt-dlp seaborn scipy --quiet

log_success "すべてのパッケージをインストール完了"

# ディレクトリ作成
log_info "ディレクトリ構成を作成中..."
mkdir -p data/videos
mkdir -p outputs/private_analysis
mkdir -p outputs/team_analysis

log_success "ディレクトリ作成完了"

# 実行権限を付与
log_info "スクリプトに実行権限を付与中..."
chmod +x analyze_private.sh

log_success "実行権限付与完了"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✓ セットアップ完了！                                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "次のステップ:"
echo ""
echo "  1. プライベート解析を実行:"
echo "     ./analyze_private.sh \"YouTube_URL\""
echo ""
echo "  2. 例:"
echo "     ./analyze_private.sh \"https://www.youtube.com/watch?v=IChwqjE0Ehw\""
echo ""
echo "  3. ローカルファイルを解析:"
echo "     ./analyze_private.sh \"data/videos/my_game.mp4\""
echo ""
echo "詳細は PRIVATE_USAGE.md をご覧ください"
echo ""
