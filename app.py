import streamlit as st
import boto3
import PyPDF2
import io
import json
from tavily import TavilyClient

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

def init_tavily_client():
    """Tavily APIクライアントを初期化"""
    try:
        tavily_client = TavilyClient(api_key=st.secrets["tavily"]["API_KEY"])
        return tavily_client
    except Exception as e:
        st.error(f"Tavily API接続エラー: {e}")
        return None

def extract_keywords_with_sonnet(bedrock_client, document_text):
    """Claude Sonnet 4を使用して文書から検索キーワードを抽出"""
    try:
        keyword_extraction_prompt = f"""
以下の決裁書から、関連情報を検索するための効果的なキーワードを抽出してください。

【決裁書内容】
{document_text[:1500]}

【指示】
1. この決裁書の内容に最も関連する検索キーワードを3-5個抽出
2. 各キーワードは具体的で検索に適したものにする
3. 業界情報、法規制、ベストプラクティスを見つけるのに有効なキーワード
4. 結果は以下の形式で出力：

キーワード1: [具体的なキーワード]
キーワード2: [具体的なキーワード]
キーワード3: [具体的なキーワード]

※キーワードのみを出力し、説明は不要です。
"""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": keyword_extraction_prompt
                    }
                ]
            }
        ]
        
        response = bedrock_client.converse(
            modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",  # Sonnet 4
            messages=messages,
            inferenceConfig={
                "maxTokens": 500
            }
        )
        
        # レスポンスから検索キーワードを抽出
        response_text = response['output']['message']['content'][0]['text']
        keywords = []
        
        for line in response_text.split('\n'):
            if 'キーワード' in line and ':' in line:
                keyword = line.split(':', 1)[1].strip()
                if keyword:
                    keywords.append(keyword)
        
        return keywords[:5]  # 最大5個
        
    except Exception as e:
        st.warning(f"キーワード抽出エラー: {e}")
        return ["決裁書 承認 ガイドライン"]  # フォールバック

def search_related_information(tavily_client, bedrock_client, document_text, enable_search=True):
    """文書内容に関連する最新情報を検索"""
    if not enable_search or not tavily_client or not bedrock_client:
        return ""
    
    try:
        # Claude Sonnet 4でキーワード抽出
        st.info("🤖 Claude Sonnet 4で検索キーワードを抽出中...")
        extracted_keywords = extract_keywords_with_sonnet(bedrock_client, document_text)
        
        if extracted_keywords:
            st.success(f"✅ 抽出されたキーワード: {', '.join(extracted_keywords)}")
        
        search_results = []
        for keyword in extracted_keywords[:3]:  # 最大3つのキーワードで検索
            try:
                response = tavily_client.search(
                    query=keyword,
                    search_depth="basic",
                    max_results=20,  # 結果数を20件
                    include_answer=True
                )
                
                if response.get('results'):
                    for result in response['results']:
                        search_results.append({
                            'title': result.get('title', ''),
                            'content': result.get('content', ''),
                            'url': result.get('url', ''),
                            'keyword': keyword
                        })
            except Exception as e:
                st.warning(f"検索キーワード '{keyword}' でエラー: {e}")
                continue
        
        # 検索結果をフォーマット
        if search_results:
            formatted_results = "\n\n=== 関連情報（AI抽出キーワード検索結果） ===\n"
            
            for i, result in enumerate(search_results[:10], 1):  # 最大10件を表示
                formatted_results += f"\n{i}. {result['title']}\n"
                formatted_results += f"内容: {result['content'][:200]}...\n"
                formatted_results += f"出典: {result['url']}\n"
                formatted_results += f"検索キーワード: {result['keyword']}\n"
            
            return formatted_results
        else:
            return ""
            
    except Exception as e:
        st.warning(f"関連情報検索エラー: {e}")
        return ""

def sanitize_text(text):
    """テキストをサニタイズ（問題のある文字を除去）"""
    if not text:
        return text
    
    # 制御文字を除去
    import re
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    # 非常に長い行を分割
    lines = sanitized.split('\n')
    sanitized_lines = []
    for line in lines:
        if len(line) > 1000:  # 1000文字を超える行は分割
            for i in range(0, len(line), 1000):
                sanitized_lines.append(line[i:i+1000])
        else:
            sanitized_lines.append(line)
    
    return '\n'.join(sanitized_lines)

def create_review_prompt(document_text, custom_prompt_template, search_results=""):
    """決裁書レビュー用のプロンプトを作成（サニタイズ付き）"""
    # テキストをサニタイズ（制御文字・長すぎる行対策）
    document_text = sanitize_text(document_text)
    
    enhanced_document_text = document_text
    if search_results:
        search_results = sanitize_text(search_results)
        enhanced_document_text = document_text + search_results
    
    prompt = custom_prompt_template.format(document_text=enhanced_document_text)
    return prompt

def stream_bedrock_response(bedrock_client, prompt):
    """Bedrock APIを使用してストリーミングレスポンスを生成（Claude Opus 4でレビュー）"""
    try:
        # プロンプト長の確認（簡素化）
        prompt_length = len(prompt)
        
        model_id = "us.anthropic.claude-opus-4-20250514-v1:0"  # Opus 4でレビュー
        
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
        
        st.divider()
        
        # 検索オプション
        st.subheader("🔍 検索設定")
        enable_search = st.checkbox(
            "関連情報をWeb検索してレビュー品質を向上",
            value=True,
            help="Tavily APIを使用して、決裁書に関連する最新情報を検索し、レビューの参考にします"
        )
    
    # メインエリア    
    uploaded_file = st.file_uploader(
        "決裁書（PDF）をアップロードしてください",
        type=['pdf'],
        help="PDFファイルのみ対応しています"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ ファイル '{uploaded_file.name}' がアップロードされました")
        
        # PDFテキスト抽出
        with st.spinner("PDF内容を読み込み中..."):
            document_text = extract_text_from_pdf(uploaded_file)
        
        if document_text:
            st.success("✅ テキスト抽出完了")
            
            # レビュー実行ボタン
            if st.button("🔍 AIレビューを開始", type="primary"):
                bedrock_client = init_bedrock_client()
                
                if bedrock_client:
                    search_results = ""
                    
                    # 関連情報検索（有効な場合）
                    if enable_search:
                        with st.spinner("関連情報を検索中..."):
                            tavily_client = init_tavily_client()
                            if tavily_client:
                                search_results = search_related_information(tavily_client, bedrock_client, document_text, enable_search)
                                if search_results:
                                    st.success("✅ 関連情報の検索完了")
                                    with st.expander("🔎 検索された関連情報"):
                                        st.markdown(search_results)
                                else:
                                    st.info("ℹ️ 追加の関連情報は見つかりませんでした")
                    
                    # プロンプト作成
                    prompt = create_review_prompt(document_text, st.session_state.get('custom_prompt', ''), search_results)
                    
                    # ストリーミングレスポンス表示
                    with st.spinner("Claude Opus 4が高品質レビューを実行中..."):
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
                                    label="📥 レビュー結果をMarkdownでダウンロード",
                                    data=full_response,
                                    file_name=f"review_{uploaded_file.name.replace('.pdf', '')}.md",
                                    mime="text/plain"
                                )
                                
                            except Exception as e:
                                st.error(f"ストリーミング処理エラー: {e}")

if __name__ == "__main__":
    main()