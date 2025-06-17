# 👨‍💼 部長AI

あなたの上司に代わって、決裁資料のレビューをしてくれるAIアプリです。

## 🌟 特徴

- **PDF書類の自動レビュー**: PDFファイルをアップロードするだけで、AI（Claude Opus 4）がレビューを実行
- **リアルタイム表示**: レビュー結果をストリーミングでリアルタイム表示
- **カスタマイズ可能**: レビューの観点や指示をカスタマイズ可能
- **製造業向け**: 製造業の決裁書レビューに特化したデフォルトプロンプト
- **結果保存**: レビュー結果をテキストファイルでダウンロード可能

## 🚀 使用方法

### 1. オンラインで使用（推奨）

Streamlit Cloudでホストされているアプリを直接使用：
[https://ai-reviewer.streamlit.app/](https://ai-reviewer.streamlit.app/)

### 2. ローカルでの実行

```bash
# リポジトリをクローン
git clone https://github.com/minorun365/ai-reviewer.git
cd ai-reviewer

# 依存関係をインストール
pip install -r requirements.txt

# 設定ファイルを作成
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# secrets.tomlにAWS認証情報を設定
# [aws]
# AWS_ACCESS_KEY_ID = "your_access_key_here"
# AWS_SECRET_ACCESS_KEY = "your_secret_key_here"
# AWS_REGION = "us-west-2"

# アプリを起動
streamlit run app.py
```

## ⚙️ 必要な設定

AWS Bedrockへのアクセス権限が必要です：

- **Claude Opus 4**モデルへのアクセス権限
- **us-west-2**リージョンでの利用
- 適切なIAMポリシーの設定

## 📋 対応ファイル形式

- PDF（.pdf）

## 🔧 技術スタック

- **Frontend**: Streamlit
- **AI Model**: AWS Bedrock Claude Opus 4
- **PDF処理**: PyPDF2
- **ホスティング**: Streamlit Cloud

## 📝 使用手順

1. **PDFアップロード**: 決裁書のPDFファイルをアップロード
2. **プロンプト調整**: 必要に応じてレビュー観点をカスタマイズ
3. **AIレビュー実行**: 「AIレビューを開始」ボタンをクリック
4. **結果確認**: リアルタイムでレビュー結果を確認
5. **結果保存**: 必要に応じてレビュー結果をダウンロード

## 🎯 レビュー観点（デフォルト）

1. 申請理由の妥当性と明確性
2. 金額・数量・期間等の具体性と妥当性
3. 承認フローや必要書類の確認
4. リスク評価と対策の検討
5. 法規制・社内規定への適合性
6. 文書の記載漏れや不備

## 🤝 コントリビューション

プルリクエストや課題の報告を歓迎します！

## 📄 ライセンス

MIT License

## 🙋‍♂️ 作成者

[@minorun365](https://github.com/minorun365)

---

**注意**: このアプリはAWSの料金が発生します。利用前にAWS Bedrockの料金体系をご確認ください。