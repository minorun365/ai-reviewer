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
最初に、作成者をねぎらうために一言褒めてあげてください。

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
        
        # 検索結果をフォーマット（文字数制限付き）
        if search_results:
            formatted_results = "\n\n=== 関連情報（AI抽出キーワード検索結果） ===\n"
            
            for i, result in enumerate(search_results[:5], 1):  # 最大5件に制限
                formatted_results += f"\n{i}. {result['title'][:80]}...\n"  # タイトルも短縮
                formatted_results += f"内容: {result['content'][:150]}...\n"  # 内容をさらに短縮
                formatted_results += f"出典: {result['url']}\n"
                formatted_results += f"検索キーワード: {result['keyword']}\n"
            
            return formatted_results
        else:
            return ""
            
    except Exception as e:
        st.warning(f"関連情報検索エラー: {e}")
        return ""

def sanitize_text_safe_encoding(text):
    """安全なエンコーディング方式でテキストをサニタイズ"""
    if not text:
        return text
    
    import base64
    import re
    
    try:
        # 方法1: 安全なASCII文字のみ保持（最もシンプル）
        # 英数字、日本語、基本的な句読点のみ許可
        safe_text = re.sub(r'[^\w\s\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\.\,\!\?\:\;\-\(\)\[\]\"\'\/]', ' ', text)
        
        # 複数の空白を単一に
        safe_text = re.sub(r'\s+', ' ', safe_text).strip()
        
        # 長すぎる場合は切り詰め
        if len(safe_text) > 8000:
            safe_text = safe_text[:8000] + "...(省略)"
        
        # ASCII互換性チェック
        try:
            safe_text.encode('ascii', errors='ignore').decode('ascii', errors='ignore')
        except:
            # ASCII化できない場合の代替処理
            safe_text = re.sub(r'[^\x20-\x7E\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', ' ', safe_text)
            safe_text = re.sub(r'\s+', ' ', safe_text).strip()
        
        return safe_text
        
    except Exception as e:
        # 全ての処理が失敗した場合の最終手段
        st.warning(f"テキスト処理で問題が発生しました: {e}")
        # 最低限の文字のみ保持
        fallback_text = re.sub(r'[^\w\s]', ' ', str(text))
        return re.sub(r'\s+', ' ', fallback_text).strip()[:5000]

def create_review_prompt(document_text, custom_prompt_template, search_results=""):
    """決裁書レビュー用のプロンプトを作成（安全なエンコーディング付き）"""
    # 新しい安全なサニタイズ方式を適用
    document_text = sanitize_text_safe_encoding(document_text)
    
    enhanced_document_text = document_text
    if search_results:
        search_results = sanitize_text_safe_encoding(search_results)
        enhanced_document_text = document_text + search_results
    
    prompt = custom_prompt_template.format(document_text=enhanced_document_text)
    return prompt

def stream_bedrock_response(bedrock_client, prompt):
    """Bedrock APIを使用してストリーミングレスポンスを生成（Claude Opus 4でレビュー）"""
    try:
        # プロンプト長の確認
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
        error_msg = str(e)
        if "ServiceUnavailableException" in error_msg:
            st.error("🚫 Bedrock APIが一時的に利用できません。プロンプトが長すぎるか、サービスが混雑している可能性があります。")
            st.info("💡 対処法: 検索機能をオフにするか、より短い文書でお試しください。")
                
        elif "ValidationException" in error_msg:
            st.error("📝 プロンプトの形式に問題があります。")
        elif "ThrottlingException" in error_msg:
            st.error("⏱️ APIのリクエスト制限に達しました。しばらく待ってから再試行してください。")
        elif "AccessDeniedException" in error_msg:
            st.error("🔑 AWS認証情報またはモデルアクセス権限を確認してください。")
        else:
            st.error(f"❌ Bedrock API呼び出しエラー: {e}")
        return None

def check_authentication():
    """認証チェック関数"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        # 中央寄せのためのレイアウト
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.title("🔐 ログイン")
            st.markdown("認証が必要です")
            
            with st.form("login_form"):
                username = st.text_input("ユーザー名")
                password = st.text_input("パスワード", type="password")
                submit_button = st.form_submit_button("ログイン", use_container_width=True)
                
                if submit_button:
                    try:
                        # デバッグ情報表示（Cloud環境での問題特定用）
                        st.write("🔍 デバッグ情報:")
                        st.write(f"入力ユーザー名: '{username}'")
                        st.write(f"入力パスワード長: {len(password)}")
                        
                        # secrets.tomlから認証情報を取得
                        correct_username = st.secrets["auth"]["username"]
                        correct_password = st.secrets["auth"]["password"]
                        
                        # デバッグ情報
                        st.write(f"設定ユーザー名: '{correct_username}'")
                        st.write(f"設定パスワード長: {len(correct_password)}")
                        st.write(f"ユーザー名一致: {username == correct_username}")
                        st.write(f"パスワード一致: {password == correct_password}")
                        
                        # パスワードの詳細デバッグ
                        st.write("🔍 パスワード詳細分析:")
                        st.write(f"入力パスワード文字コード: {[ord(c) for c in password]}")
                        st.write(f"設定パスワード文字コード: {[ord(c) for c in correct_password]}")
                        st.write(f"入力パスワード repr: {repr(password)}")
                        st.write(f"設定パスワード repr: {repr(correct_password)}")
                        
                        # 文字単位で比較
                        if len(password) == len(correct_password):
                            for i, (c1, c2) in enumerate(zip(password, correct_password)):
                                if c1 != c2:
                                    st.write(f"位置{i}: 入力'{c1}'({ord(c1)}) vs 設定'{c2}'({ord(c2)})")
                        
                        # トリム後の比較
                        trimmed_password = password.strip()
                        trimmed_correct = correct_password.strip()
                        st.write(f"トリム後一致: {trimmed_password == trimmed_correct}")
                        
                        if username == correct_username and password == correct_password:
                            st.session_state.authenticated = True
                            st.success("✅ ログイン成功！")
                            st.rerun()
                        else:
                            st.error("❌ ユーザー名またはパスワードが間違っています")
                    except Exception as e:
                        st.error(f"❌ 認証設定エラー: {e}")
                        st.write(f"エラー詳細: {type(e).__name__}: {str(e)}")
                        
                        # secrets の構造をデバッグ
                        try:
                            st.write("Secrets構造:")
                            st.write(f"auth セクション存在: {'auth' in st.secrets}")
                            if 'auth' in st.secrets:
                                st.write(f"username キー存在: {'username' in st.secrets['auth']}")
                                st.write(f"password キー存在: {'password' in st.secrets['auth']}")
                        except:
                            st.write("Secrets構造の確認でエラー")
                        
                        st.info("💡 .streamlit/secrets.toml ファイルに認証情報を設定してください")
        
        return False
    
    return True

def main():
    st.set_page_config(
        page_title="部長AI",
        page_icon="👨‍💼",
        layout="wide"
    )
    
    # 認証チェック
    if not check_authentication():
        return
    
    # ログアウトボタンをサイドバーに追加
    with st.sidebar:
        if st.button("🚪 ログアウト"):
            st.session_state.authenticated = False
            st.rerun()
    
    st.title("👨‍💼 部長AI")
    st.markdown("あなたの上司に代わって、決裁資料のレビューをします！")
    
    # サイドバーでレビュープロンプト設定
    with st.sidebar:
        st.header("⚙️ レビュー設定")
        
        # デフォルトプロンプトテンプレート
        default_prompt = """あなたは製造業の情シス部門の経験豊富な上司として、添付の決裁書をレビューしてください。

【レビュー観点】
- 資料はまず冒頭で「何の決裁が欲しいのか」を明確にしてほしい。目的が不明なまま説明が始まると良くない。
- 「良い資料」の条件は、ひとりよがりにならず、「読む人の立場とレベル」を理解して書かれていることである。
- 説明の構成と資料の順番が合っているさか確認してほしい (当日、スライドをあちこち移動しなくて済むように練ってほしい)
- 最も重視する要素の1つが「コストの妥当性」
- 常に「ユーザー目線」を優先し、インフラ部門(自分たち)の都合でユーザーに迷惑がかかるような提案は認めない。

【追加のアドバイス観点】
- 上記以外にも、一般的なレビュー準備の観点で必要と思われる点があれば、追加でアドバイスをしてください。
- 決裁説明時の時間配分のアドバイスも添えてください。60分の会議時間の場合、各セクションの所要時間目安と、質疑応答の時間も加味してください。

【決裁書内容】
{document_text}"""
        
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