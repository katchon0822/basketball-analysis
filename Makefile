# Basketball Analysis Makefile
# Docker環境の簡単操作用

.PHONY: help build up down logs shell clean test analyze-three analyze-finals

help: ## このヘルプを表示
	@echo "Basketball Analysis - Make コマンド一覧"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Dockerイメージをビルド
	docker-compose build

up: ## コンテナを起動（フォアグラウンド）
	docker-compose up

up-d: ## コンテナを起動（バックグラウンド）
	docker-compose up -d

down: ## コンテナを停止・削除
	docker-compose down

logs: ## ログを表示（リアルタイム）
	docker-compose logs -f

shell: ## コンテナ内でbashを起動
	docker-compose run --rm basketball-analysis bash

clean: ## 全コンテナ・イメージ・ボリュームを削除
	docker-compose down --rmi all -v
	docker system prune -f

test: ## テスト実行
	docker-compose run --rm basketball-analysis python -m pytest tests/

# === 分析タスク ===

analyze-three: ## 3試合の自動分析
	docker-compose run --rm basketball-analysis python analyze_three_games_fast.py

analyze-finals: ## 2024 NBA Finals分析
	docker-compose run --rm basketball-analysis python run_finals_hc_analysis.py

analyze-hachimura: ## 八村塁選手分析
	docker-compose run --rm basketball-analysis python generate_hachimura_3d_heatmap.py

# === 動画ダウンロード ===

download-game1: ## 試合2-1ダウンロード
	docker-compose run --rm basketball-analysis yt-dlp "https://youtu.be/MiI8X2-tZdA" -f "best[height<=720]" -o "data/videos/game_2-1.mp4"

download-game2: ## 試合2-2ダウンロード
	docker-compose run --rm basketball-analysis yt-dlp "https://youtu.be/UWvM4Z5lqbE" -f "best[height<=720]" -o "data/videos/game_2-2.mp4"

download-game3: ## 試合2-3ダウンロード
	docker-compose run --rm basketball-analysis yt-dlp "https://youtu.be/I4sxn0IJkGE" -f "best[height<=720]" -o "data/videos/game_2-3.mp4"

download-all: download-game1 download-game2 download-game3 ## 全動画ダウンロード

# === 開発用 ===

rebuild: ## キャッシュなしで再ビルド
	docker-compose build --no-cache

ps: ## 実行中のコンテナ一覧
	docker-compose ps

top: ## コンテナのリソース使用状況
	docker-compose top

# === ワンライナー実行例 ===

# make build && make analyze-three
# make download-all && make analyze-three
