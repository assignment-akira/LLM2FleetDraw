# LLM2FleetDraw

ROS 2 Humble / turtlesim を使った複数ロボット協調描画の課題プロトタイプです。画像を中心線・ストロークへ変換し、RCB または K-means で分担して複数台のカメが描きます。

## システム構成

- **FastAPI** (`ai_planner/app.py`): AIプランナー用のHTTP APIエンドポイント
- **Ollama**: 言語モデル推論サーバ
- **Qwen3**: 自然言語指示を解釈するLLM
- **Stable Diffusion 1.5 + Logo.Redmond LoRA**: 描画対象の画像生成
- **OpenCV**: 中心線・ストローク抽出
- **RCB / K-means**: ストロークの割当
- **ROS 2 Humble + turtlesim**: 各カメの位置フィードバック制御と描画

上記要素は段階的に動作確認したものです。この公開用最小構成のみから、自然言語入力から描画までを一括実行できるとは限りません。

## 動作環境

- Linux / WSL2 Ubuntu 22.04
- Docker Engine と Docker Compose plugin
- GUI表示用のX11 / WSLgなど
- GPU画像生成には NVIDIA GPU と DockerでのGPU実行環境が必要

Dockerfileに記載されたPython依存関係はビルド時に取得します。学習済みモデル・LoRA重みは公開リポジトリに含めません。

## 最小の起動確認

プロジェクト直下で：

```bash
sudo docker compose -f compose.yaml up -d ros2-fleet
sudo docker compose -f compose.yaml ps
```

turtlesimのGUIを起動：

```bash
sudo docker compose -f compose.yaml exec ros2-fleet bash -lc \
  'source /opt/ros/humble/setup.bash && ros2 run turtlesim turtlesim_node'
```

別端末で状態確認：

```bash
sudo docker compose -f compose.yaml exec -T ros2-fleet bash -lc \
  'source /opt/ros/humble/setup.bash && ros2 topic list'
```

ここまでが公開済みのDocker構成を前提とした基本動作確認です。画像生成・分担・描画を通す際には、`sd15_eval/`、`batch_partition_v1/`、`ros2_fleet/one_turtle_logo/`の各モジュールと入力計画JSONを組み合わせます。個別の実験ランナーは公開用最小構成から除いています。

## データと制御

- ストロークはウェイポイントの座標列として表します。
- 分担はストロークの重複・欠落がないように割り当てます。
- 各カメは`/turtleN/pose`の位置・姿勢を使い、`/turtleN/cmd_vel`に指令します。
- 描画開始・終了では到達許容誤差および実速度の停止確認を行い、`/turtleN/set_pen`を切り替えます。

## 実験の概要

ロボット・カメ・花を対象として3台／5台のストローク分担を実測。RCBとK-meansを比較しました。主要な知見は、ペン切替前の端点到達精度と停止確認が、分担描画の接続品質を改善した点です。台数による所要時間短縮は補助的な結果です。

## 今後の課題

自然言語からの全処理統合、分担方式の品質評価、障害時の再割当、実機ロボットへの展開。

## 公開に関する注意

モデル重み、個人の実験ログ、動画、認証情報は含めません。外部LoRA・モデルの利用時には、それぞれの配布条件を確認してください。
