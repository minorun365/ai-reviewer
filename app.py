import streamlit as st
import boto3
import PyPDF2
import io
import json

def init_bedrock_client():
    """AWS Bedrockクライアントを初期化"""
    try:
        bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=st.secrets["aws"]["AWS_REGION"],
            aws_access_key_id=st.secrets["aws"]["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=st.secrets["aws"]["AWS_SECRET_ACCESS_KEY"]
        )
        return bedrock_client
    except Exception as e:
        st.error(f"AWS Bedrock接続エラー: {e}")
        return None

def extract_text_from_pdf(pdf_file):
    """PDFファイルからテキストを抽出"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"PDF読み込みエラー: {e}")
        return None

def create_review_prompt(document_text, custom_prompt_template):
    """決裁書レビュー用のプロンプトを作成"""
    prompt = custom_prompt_template.format(document_text=document_text)
    return prompt

def stream_bedrock_response(bedrock_client, prompt):
    """Bedrock APIを使用してストリーミングレスポンスを生成"""
    try:
        model_id = "us.anthropic.claude-opus-4-20250514-v1:0"
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
        
        response = bedrock_client.converse_stream(
            modelId=model_id,
            messages=messages,
            inferenceConfig={
                "maxTokens": 4000
            }
        )
        
        return response
        
    except Exception as e:
        st.error(f"Bedrock API呼び出しエラー: {e}")
        return None

def main():
    st.set_page_config(
        page_title="部長AI",
        page_icon="👨‍💼",
        layout="wide"
    )
    
    st.title("👨‍💼 部長AI")
    st.markdown("あなたの上司に代わって、決裁資料のレビューをします！")
    
    # サイドバーでレビュープロンプト設定
    with st.sidebar:
        st.header("⚙️ レビュー設定")
        
        # デフォルトプロンプトテンプレート
        default_prompt = """あなたは製造業の経験豊富な上司として、以下の決裁書をレビューしてください。

【レビュー観点】
1. 申請理由の妥当性と明確性
2. 金額・数量・期間等の具体性と妥当性
3. 承認フローや必要書類の確認
4. リスク評価と対策の検討
5. 法規制・社内規定への適合性
6. 文書の記載漏れや不備

【決裁書内容】
{document_text}

【レビュー結果】
上記の観点から、具体的な指摘事項と改善提案を日本語で出力してください。
承認可能な場合はその旨も明記し、要改善点がある場合は優先度を付けて説明してください。"""
        
        custom_prompt = st.text_area(
            "レビュープロンプト",
            value=default_prompt,
            height=600,
            help="プロンプト内で {document_text} を使用すると、PDFの内容が挿入されます"
        )
        
        if st.button("プロンプトをリセット"):
            st.session_state.custom_prompt = default_prompt
            st.rerun()
            
        # セッション状態にプロンプトを保存
        st.session_state.custom_prompt = custom_prompt
    
    # メインエリア    
    uploaded_file = st.file_uploader(
        "決裁書（PDF）をアップロードしてください",
        type=['pdf'],
        help="PDFファイルのみ対応しています"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ ファイル '{uploaded_file.name}' がアップロードされました")
        
        # PDFテキスト抽出
        with st.spinner("📖 PDF内容を読み込み中..."):
            document_text = extract_text_from_pdf(uploaded_file)
        
        if document_text:
            st.success("✅ テキスト抽出完了")
            
            # 抽出されたテキストのプレビュー
            with st.expander("📄 抽出されたテキストのプレビュー"):
                st.text_area("内容", document_text[:1000] + "..." if len(document_text) > 1000 else document_text, height=200)
            
            # レビュー実行ボタン
            if st.button("🔍 AIレビューを開始", type="primary"):
                bedrock_client = init_bedrock_client()
                
                if bedrock_client:                    
                    # プロンプト作成
                    prompt = create_review_prompt(document_text, st.session_state.get('custom_prompt', ''))
                    
                    # ストリーミングレスポンス表示
                    with st.spinner("AIがレビューを実行中..."):
                        response_stream = stream_bedrock_response(bedrock_client, prompt)
                        
                        if response_stream:
                            # ストリーミング結果を表示するコンテナ
                            response_container = st.empty()
                            full_response = ""
                            
                            try:
                                for event in response_stream['stream']:
                                    if 'contentBlockDelta' in event:
                                        delta = event['contentBlockDelta']['delta']
                                        if 'text' in delta:
                                            full_response += delta['text']
                                            response_container.markdown(full_response)
                                
                                # 最終結果の保存オプション
                                st.success("✅ レビュー完了")
                                
                                # ダウンロードボタン
                                st.download_button(
                                    label="📥 レビュー結果をダウンロード",
                                    data=full_response,
                                    file_name=f"review_{uploaded_file.name.replace('.pdf', '')}.md",
                                    mime="text/plain"
                                )
                                
                            except Exception as e:
                                st.error(f"ストリーミング処理エラー: {e}")

if __name__ == "__main__":
    main()