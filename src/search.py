import chromadb
from chromadb.config import Settings
import ollama
import json
from pathlib import Path
import pandas as pd

class DuelMastersHybridSearch:
    def __init__(self):
        script_dir = Path(__file__).parent
        
        # ChromaDB クライアント初期化
        self.chroma_client = chromadb.PersistentClient(
            path=str(script_dir / "chroma_db"),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # コレクション取得
        self.collection = self.chroma_client.get_collection("duel_masters_cards")
        
        # カードデータをDataFrameとして保持
        self.cards_df = pd.read_csv(
            script_dir / "data" / "cards.csv",
            encoding="utf-8",
            on_bad_lines='skip',
            engine='python'
        )
        
        # 用語集を読み込み（dataフォルダ内）
        glossary_path = script_dir / "data" / "duelmasters_glossary.json"
        if glossary_path.exists():
            with open(glossary_path, "r", encoding="utf-8") as f:
                self.glossary = json.load(f)
        else:
            self.glossary = {}
            print("⚠️  用語集が見つかりません")
        
        # 公式キーワードを読み込み
        keywords_path = script_dir / "keywords.txt"
        self.official_keywords = []
        if keywords_path.exists():
            with open(keywords_path, "r", encoding="utf-8") as f:
                self.official_keywords = [line.strip() for line in f if line.strip()]
        else:
            print("⚠️  keywords.txtが見つかりません")
        
        print("✅ データベース接続完了")
        print(f"カードデータ: {len(self.cards_df)}枚読み込み")
        if self.glossary:
            print(f"用語集: 読み込み完了")
        if self.official_keywords:
            print(f"公式キーワード: {len(self.official_keywords)}件読み込み完了")
    
    def build_glossary_examples(self):
        """用語集から検索例を生成"""
        if not self.glossary:
            return ""
        
        examples = []
        
        # リソース増加の例
        if "リソース増加" in self.glossary:
            examples.append("\n**リソース増加の表現バリエーション:**")
            
            # マナ増加
            mana = self.glossary["リソース増加"]["マナ増加"]
            mana_terms = mana["正式表現"] + mana.get("キーワード能力", []) + mana.get("俗語", [])
            examples.append(f"• マナ増加: {', '.join(mana_terms[:5])}")
            
            # 手札増加
            hand = self.glossary["リソース増加"]["手札増加"]
            hand_terms = hand["正式表現"] + hand.get("俗語", [])
            examples.append(f"• 手札増加: {', '.join(hand_terms[:5])}")
            
            # 墓地回収
            grave = self.glossary["リソース増加"]["墓地回収"]
            grave_terms = grave["正式表現"] + grave.get("俗語", [])
            examples.append(f"• 墓地回収: {', '.join(grave_terms[:3])}")
        
        # 除去の例
        if "除去" in self.glossary:
            examples.append("\n**除去の種類:**")
            for removal_type in ["破壊", "バウンス", "山札送り"]:
                if removal_type in self.glossary["除去"]:
                    data = self.glossary["除去"][removal_type]
                    terms = data.get("正式表現", []) + data.get("俗語", [])
                    examples.append(f"• {removal_type}: {', '.join(terms[:3])}")
        
        # 俗語の例
        if "俗語・スラング" in self.glossary:
            examples.append("\n**よく使われる俗語:**")
            slang_examples = ["メクレイド", "鬼回り", "事故", "刺さる"]
            for term in slang_examples:
                if term in self.glossary["俗語・スラング"]:
                    desc = self.glossary["俗語・スラング"][term]["説明"]
                    examples.append(f"• {term}: {desc}")
        
        return "\n".join(examples)
    
    def extract_search_conditions(self, query):
        """LLMで検索条件を抽出（用語集を活用）"""
        print("検索条件を抽出中...")
        
        glossary_examples = self.build_glossary_examples()
        
        # 公式キーワードリストを整形（見やすく）
        keywords_list = ""
        if self.official_keywords:
            # 10個ずつ改行
            keywords_chunks = [self.official_keywords[i:i+10] for i in range(0, len(self.official_keywords), 10)]
            keywords_list = "\n**公式キーワード能力の完全リスト:**\n"
            for chunk in keywords_chunks:
                keywords_list += "- " + ", ".join(chunk) + "\n"
        
        prompt = f"""ユーザーの検索クエリから、カード検索の条件を抽出してください。

検索クエリ: 「{query}」

以下のJSON形式で条件を返してください：

{{
  "cost_min": null,
  "cost_max": null,
  "civilizations": [],
  "card_types": [],
  "keywords": [],
  "race_keywords": [],
  "effect_groups": [],
  "exclude_keywords": [],
  "general_search": []
}}

{keywords_list}

**用語集を参考にしてください：**
{glossary_examples}

**重要ルール:**

1. **自分と相手の区別（超重要）:**
   - 「相手」が明示されていない限り、リソース増加は**自分のもの**
   - 例: "マナが増える" → 自分のマナが増える
   - 例: "相手のマナを破壊" → 相手への干渉（exclude_keywords不要）

2. **general_search（新機能）:**
   - **全カラム**（card_name, civilization, color_type, card_type, cost, power, race, text）を対象に検索
   - カード名、文明、種族、効果テキスト、パワー、コストなど、どこかに含まれていればOK
   - 公式キーワード能力、種族名、カード名の一部など、包括的に検索
   - 例: "ジャストダイバー" → general_search: ["ジャストダイバー"]
   - 例: "進化クリーチャー" → general_search: ["進化"]
   - 例: "レクスターズ" → general_search: ["レクスターズ"]
   - 例: "シールドトリガー" → general_search: ["S・トリガー", "シールド・トリガー"]
   - 例: "10000パワー" → general_search: ["10000"]

3. **effect_groups の使い方:**
   - 2重配列です。各グループは文字列の配列です。
   - 各グループ内はOR条件、グループ間はAND条件
   - 用語集のバリエーションを活用してください
   
   例1: "マナが増える"
   → effect_groups: [["マナゾーンに置", "マナに加え", "マナチャージ", "チャージャー"]]
   
   例2: "手札、マナ、墓地を同時に増やす"
   → effect_groups: [
       ["手札に加", "ドロー", "引く", "カードを引"],
       ["マナゾーンに置", "マナに加え", "マナチャージ"],
       ["墓地に置", "墓地から", "墓地回収"]
     ]
   
   例3: "革命チェンジ先のドラゴン"
   → keywords: ["革命チェンジ"], race_keywords: ["ドラゴン"], effect_groups: []
   （キーワード能力は keywords に入れる。effect_groups は効果の内容を検索する時のみ使用）

4. **keywords（超超超重要）:**
   - **上記の公式キーワード能力リストに含まれるもののみ**を入れる
   - このリストに無いものは絶対にkeywordsに入れないでください
   - 俗語（ランデス、バウンス、マナブースト、サーチなど）は**絶対に**keywordsに入れない
   
   ❌ 悪い例:
   - keywords: ["ランデス"] → ランデスは俗語（リストに無い）
   - keywords: ["バウンス"] → バウンスは俗語（リストに無い）
   - keywords: ["マナブースト"] → マナブーストは俗語（リストに無い）
   - keywords: ["サーチ"] → サーチは俗語（リストに無い）
   
   ✅ 良い例:
   - keywords: ["革命チェンジ"] → 公式キーワード（リストにある）
   - keywords: ["スピードアタッカー"] → 公式キーワード（リストにある）
   - keywords: ["侵略"] → 公式キーワード（リストにある）
   - keywords: ["S・トリガー"] → 公式キーワード（リストにある）

5. **文明の指定:**
   - "光" → civilizations: ["光"]
   - "火文明" → civilizations: ["火"]
   - "光のシールドトリガー" → civilizations: ["光"], keywords: ["S・トリガー"]

6. **種族の指定:**
   - race_keywords: 厳密に種族フィールドで検索
   - general_search: カード名、種族、効果テキスト全体で検索
   
   例: "レクスターズのクリーチャー"
   → card_types: ["クリーチャー"], general_search: ["レクスターズ"]

7. **俗語の変換:**
   - "メクレイド" → effect_groups: [["メクレイド"]]（種族は指定しない）
   - "サイバーメクレイド" → race_keywords: ["サイバー"], effect_groups: [["メクレイド"]]
   - "アーマードメクレイド" → race_keywords: ["アーマード"], effect_groups: [["メクレイド"]]
   - "ハンデス" → effect_groups: [["相手の手札", "手札を捨て"]]
   - "サーチ" → effect_groups: [["山札から探す", "山札をみて", "山札から手札"]]
   - "ランデス" → effect_groups: [["相手のマナゾーンから", "マナ破壊"]]
   - "バウンス" → effect_groups: [["手札に戻す", "持ち主の手札"]]
   
   **重要:** 
   - 「メクレイド」単体の場合、race_keywordsは空にする（全種族対象）
   - 「◯◯メクレイド」の場合のみ、race_keywordsに種族を指定

8. **コスト指定:**
   - "軽量" → cost_max: 3
   - "中量" → cost_min: 4, cost_max: 6
   - "重量" → cost_min: 7
   - "3コスト以下" → cost_max: 3
   - "5コスト以上" → cost_min: 5

9. **カードタイプ:**
   - "呪文" → card_types: ["呪文"]
   - "クリーチャー" → card_types: ["クリーチャー"]
   - "軽量呪文" → card_types: ["呪文"], cost_max: 3

10. **完全な例:**
   - "バウンスできる軽量呪文"
   → card_types: ["呪文"], cost_max: 3, effect_groups: [["手札に戻す", "持ち主の手札"]]
   
   - "マナブーストできる軽量呪文"
   → card_types: ["呪文"], cost_max: 3, effect_groups: [["マナゾーンに置", "マナに加え", "チャージャー"]]
   
   - "ランデスできる呪文"
   → card_types: ["呪文"], effect_groups: [["相手のマナゾーンから", "マナ破壊"]]
   
   - "ジャストダイバー"
   → keywords: ["ジャストダイバー"]（公式キーワードリストにあるので）
   
   - "進化クリーチャー"
   → card_types: ["クリーチャー"], general_search: ["進化"]


**必ずJSONのみを出力してください。説明は不要です。**"""

        response = ollama.chat(
            model='llama3.1:8b',
            messages=[
                {
                    'role': 'system',
                    'content': 'あなたはデュエル・マスターズのカード検索システムです。用語集を活用し、正確に条件を抽出してください。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            options={'temperature': 0.1}
        )
        
        # JSONをパース
        try:
            response_text = response['message']['content']
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            conditions = json.loads(response_text.strip())
            
            # 公式キーワードリストを使って俗語をkeywordsから除外
            if conditions.get('keywords') and self.official_keywords:
                # 公式キーワードのみ残す（リストに含まれるもののみ）
                original_keywords = conditions['keywords'].copy()
                conditions['keywords'] = [
                    kw for kw in conditions['keywords'] 
                    if kw in self.official_keywords
                ]
                
                # 除外された俗語をログ出力
                removed = set(original_keywords) - set(conditions['keywords'])
                if removed:
                    print(f"ℹ️  非公式キーワードをkeywordsから除外: {removed}")
                    print(f"   （公式キーワードリストに無いため）")
            
            print(f"抽出された条件: {json.dumps(conditions, ensure_ascii=False, indent=2)}")
            return conditions
            
        except Exception as e:
            print(f"⚠️  条件抽出エラー: {e}")
            print(f"レスポンス: {response_text[:200]}")
            return {}
    
    def filter_by_conditions(self, conditions):
        """Pythonで明確な条件のみフィルタリング（厳密版）"""
        print("条件でフィルタリング中...")
        
        df = self.cards_df.copy()
        original_count = len(df)
        
        # コストでフィルタ
        if conditions.get('cost_min') is not None:
            df = df[pd.to_numeric(df['cost'], errors='coerce') >= conditions['cost_min']]
        if conditions.get('cost_max') is not None:
            df = df[pd.to_numeric(df['cost'], errors='coerce') <= conditions['cost_max']]
        
        # 文明でフィルタ（厳密版）
        if conditions.get('civilizations'):
            civs = conditions['civilizations']
            # 文明は厳密に一致させる（「水」なら必ず「水」が含まれる）
            df = df[df['civilization'].apply(
                lambda x: any(civ in str(x) for civ in civs) if pd.notna(x) else False
            )]
            print(f"   文明フィルタ適用: {civs} → {len(df)}枚")
        
        # カードタイプでフィルタ
        if conditions.get('card_types'):
            types = conditions['card_types']
            df = df[df['card_type'].apply(
                lambda x: any(t in str(x) for t in types) if pd.notna(x) else False
            )]
        
        # キーワードでフィルタ（重要なキーワードは厳密に）
        if conditions.get('keywords'):
            # 特に厳密にフィルタすべきキーワード（検索で重要度が高い）
            high_priority_keywords = [
                'S・トリガー', 'スーパー・S・トリガー', 'S・トリガー・プラス',
                '侵略', 'S級侵略', 'SSS級侵略', '侵略ZERO',
                '革命チェンジ', 'P革命チェンジ',
                'スピードアタッカー', 'マッハファイター',
                'ブロッカー'
            ]
            
            for keyword in conditions['keywords']:
                # 公式キーワードリストに含まれているか確認
                if keyword not in self.official_keywords:
                    print(f"   ⚠️  警告: '{keyword}' は公式キーワードリストに含まれていません（スキップ）")
                    continue
                
                # 高優先度キーワードかチェック
                is_high_priority = keyword in high_priority_keywords
                
                if is_high_priority:
                    # 厳密一致（必ず含む）
                    df = df[df['text'].apply(
                        lambda x: keyword in str(x) if pd.notna(x) else False
                    )]
                    print(f"   厳密キーワードフィルタ: {keyword} → {len(df)}枚")
                else:
                    # 通常キーワード
                    df = df[df['text'].apply(
                        lambda x: keyword in str(x) if pd.notna(x) else False
                    )]
        
        # 種族でフィルタ
        if conditions.get('race_keywords'):
            for race_kw in conditions['race_keywords']:
                df = df[df['race'].apply(
                    lambda x: race_kw in str(x) if pd.notna(x) else False
                )]
        
        # 全体検索（全カラム対象：card_name, civilization, color_type, card_type, cost, power, race, text）
        if conditions.get('general_search'):
            for search_term in conditions['general_search']:
                # すべてのカラムのいずれかに含まれていればOK
                df = df[df.apply(
                    lambda row: (
                        (pd.notna(row.get('card_name')) and search_term in str(row['card_name'])) or
                        (pd.notna(row.get('civilization')) and search_term in str(row['civilization'])) or
                        (pd.notna(row.get('color_type')) and search_term in str(row['color_type'])) or
                        (pd.notna(row.get('card_type')) and search_term in str(row['card_type'])) or
                        (pd.notna(row.get('cost')) and search_term in str(row['cost'])) or
                        (pd.notna(row.get('power')) and search_term in str(row['power'])) or
                        (pd.notna(row.get('race')) and search_term in str(row['race'])) or
                        (pd.notna(row.get('text')) and search_term in str(row['text']))
                    ),
                    axis=1
                )]
        
        # 効果グループでフィルタ（グループ内OR、グループ間AND）
        if conditions.get('effect_groups'):
            effect_groups = conditions['effect_groups']
            
            # effect_groupsの検証と修正
            validated_groups = []
            for group in effect_groups:
                # 3重配列の場合は平坦化
                if isinstance(group, list) and len(group) > 0 and isinstance(group[0], list):
                    print(f"⚠️  3重配列を検出、修正中: {group}")
                    group = group[0]  # 最初の要素を取り出す
                
                # グループが文字列のリストであることを確認
                if isinstance(group, list) and all(isinstance(item, str) for item in group):
                    validated_groups.append(group)
                else:
                    print(f"⚠️  不正なグループをスキップ: {group}")
            
            # 検証済みグループでフィルタ
            for group in validated_groups:
                df = df[df['text'].apply(
                    lambda x: any(keyword in str(x) for keyword in group) if pd.notna(x) else False
                )]
        
        # 除外キーワードでフィルタ（相手への干渉を除外など）
        if conditions.get('exclude_keywords'):
            for exclude_kw in conditions['exclude_keywords']:
                df = df[df['text'].apply(
                    lambda x: exclude_kw not in str(x) if pd.notna(x) else True
                )]
        
        filtered_count = len(df)
        print(f"✅ フィルタ結果: {original_count}枚 → {filtered_count}枚")
        
        return df
    
    def generate_embedding(self, text):
        """テキストをベクトル化"""
        response = ollama.embeddings(
            model='nomic-embed-text',
            prompt=text
        )
        return response['embedding']
    
    def rank_by_vector_search(self, filtered_df, query, conditions, top_k=50):
        """ベクトル検索でランキング（完全一致ボーナス付き）"""
        if len(filtered_df) == 0:
            return filtered_df
        
        print(f"ベクトル検索でランキング中... (上位{min(top_k, len(filtered_df))}件)")
        
        query_embedding = self.generate_embedding(query)
        filtered_ids = [f"card_{idx}" for idx in filtered_df.index]
        
        try:
            results = self.collection.get(
                ids=filtered_ids,
                include=['embeddings']
            )
            
            if not results['ids']:
                return filtered_df.head(top_k)
            
            import numpy as np
            embeddings = np.array(results['embeddings'])
            query_emb = np.array(query_embedding)
            
            # コサイン類似度
            similarities = np.dot(embeddings, query_emb) / (
                np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_emb)
            )
            
            # 完全一致ボーナスを追加
            for i, card_id in enumerate(results['ids']):
                card_idx = int(card_id.replace('card_', ''))
                card = filtered_df.loc[card_idx]
                bonus = 0.0
                
                # 文明の完全一致ボーナス（重要度: 高）
                if conditions.get('civilizations'):
                    for civ in conditions['civilizations']:
                        if pd.notna(card['civilization']) and civ in str(card['civilization']):
                            bonus += 0.5  # 高いボーナス
                            print(f"   文明一致ボーナス: {card['card_name']} (+0.5)")
                
                # キーワードの完全一致ボーナス（重要度: 高）
                if conditions.get('keywords'):
                    for kw in conditions['keywords']:
                        if pd.notna(card['text']) and kw in str(card['text']):
                            bonus += 0.3  # 高いボーナス
                            print(f"   キーワード一致ボーナス: {card['card_name']} (+0.3)")
                
                # 種族の完全一致ボーナス
                if conditions.get('race_keywords'):
                    for race_kw in conditions['race_keywords']:
                        if pd.notna(card['race']) and race_kw in str(card['race']):
                            bonus += 0.2
                            print(f"   種族一致ボーナス: {card['card_name']} (+0.2)")
                
                # 効果グループの一致ボーナス
                if conditions.get('effect_groups'):
                    for group in conditions['effect_groups']:
                        if isinstance(group, list):
                            for effect_kw in group:
                                if pd.notna(card['text']) and effect_kw in str(card['text']):
                                    bonus += 0.15
                                    print(f"   効果一致ボーナス: {card['card_name']} (+0.15)")
                                    break  # グループ内は1回のみ
                
                # ボーナスを適用（類似度は[-1, 1]の範囲なので、ボーナスで確実に上位に）
                similarities[i] += bonus
            
            sorted_indices = np.argsort(similarities)[::-1][:top_k]
            sorted_ids = [results['ids'][i] for i in sorted_indices]
            
            card_indices = [int(id.replace('card_', '')) for id in sorted_ids]
            return filtered_df.loc[card_indices]
            
        except Exception as e:
            print(f"⚠️  ベクトル検索エラー: {e}")
            return filtered_df.head(top_k)
    
    def search(self, query, max_display=10):
        """ハイブリッド検索（最終版）"""
        print(f"\n{'='*60}")
        print(f"検索クエリ: {query}")
        print(f"{'='*60}\n")
        
        # Step 1: 明確な条件を抽出
        conditions = self.extract_search_conditions(query)
        
        # Step 2: 条件でフィルタリング
        filtered_df = self.filter_by_conditions(conditions) if conditions else self.cards_df.copy()
        
        if len(filtered_df) == 0:
            print("❌ 条件に合うカードが見つかりませんでした")
            return None
        
        # Step 3: ベクトル検索でランキング（完全一致ボーナス付き）
        ranked_df = self.rank_by_vector_search(filtered_df, query, conditions, top_k=50)
        
        # Step 4: 結果表示
        print(f"\n{'='*60}")
        print(f"検索結果: {len(ranked_df)}件")
        print(f"{'='*60}\n")
        
        for i, (idx, card) in enumerate(ranked_df.head(max_display).iterrows(), 1):
            print(f"【{i}】{card['card_name']}")
            print(f"   文明: {card['civilization']} | タイプ: {card['card_type']}")
            print(f"   コスト: {card['cost']} | パワー: {card['power']}")
            if pd.notna(card['race']) and str(card['race']) != 'nan':
                print(f"   種族: {card['race']}")
            if pd.notna(card['text']):
                text = str(card['text'])[:200] + "..." if len(str(card['text'])) > 200 else str(card['text'])
                print(f"   効果: {text}")
            print()
        
        if len(ranked_df) > max_display:
            print(f"... 他 {len(ranked_df) - max_display} 件")
        
        return ranked_df

def main():
    searcher = DuelMastersHybridSearch()
    
    print("\n" + "="*60)
    print("対話モード - 自由に検索できます")
    print("="*60)
    print("検索したいカードの条件を入力してください（終了: end）\n")
    
    while True:
        query = input("検索> ")
        if query.lower() in ['end', 'exit']:
            print("終了します")
            break
        
        if query.strip():
            searcher.search(query)

if __name__ == "__main__":
    main()